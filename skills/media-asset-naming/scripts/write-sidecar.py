#!/usr/bin/env python3
"""write-sidecar.py — write an asset's machine-readable sidecar and update the project manifest.

The orchestration close-the-loop step: the generation MCP has no name/metadata field, so after a
generation is downloaded and named to the convention (references/conventions.md), this records the
metadata a filename cannot hold. Two halves, by design:

  1. GEN-TIME truth (lossless): --prompt, --model, --ratio, --ref come from the agent's own
     generate_image call args. The full prompt and reference lineage only exist there.
  2. READ-BACK enrichment (reconciliation): --enrich-json takes the real Runway `list_recent`
     payload (a single asset object OR the full {"assets":[...]}), matched by task id, and fills the
     verified technical + lineage fields the read-back API actually returns: dimensions, aspect
     ratio, real createdAt, remote asset id, parentAssetGroupId (batch/turnaround grouping),
     sourceAssetId (edit lineage), isUserUpload, fileSize, and model (from the asset URL path).

This is what lets an agent reconcile a downloaded asset WITHOUT re-analyzing the image (no vision
tokens): the metadata is read from the API payload, not the pixels. Seed is intentionally absent —
Runway's image models do not expose one, so seed stays null and reproducibility rests on
model + full prompt + refs.

Sidecar path = asset path with a .json extension. Also updates the project _manifest.json (keyed by
basename) so a workflow queries by field instead of scanning filenames. Idempotent.

Usage:
  write-sidecar.py ASSET.png --project spring-launch --category sheet --subject ava \\
      --descriptor master --version 1 --status work \\
      --tool runway --model gpt-image-2 --task-id <id> --prompt "..." \\
      [--ref <id> --ref <id>] [--ai-generated] \\
      [--enrich-json list_recent.json]         # reconcile technical/lineage fields from the API
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# extension -> OMC structural type. The essence's "what it is".
STRUCTURAL = {
    ".png": "digital.image", ".jpg": "digital.image", ".jpeg": "digital.image",
    ".webp": "digital.image", ".gif": "digital.image",
    ".mp4": "digital.movingImage", ".mov": "digital.movingImage",
    ".wav": "digital.audio", ".mp3": "digital.audio", ".m4a": "digital.audio",
}
# category -> OMC-ish functional type. The "how it is used".
FUNCTIONAL = {
    "char": "artwork.characterDesign", "loc": "artwork.environment",
    "scene": "artwork.scene", "style": "artwork.styleFrame",
    "sheet": "artwork.referenceSheet", "shot": "video.shot",
    "cut": "video.editedSequence", "misc": "artwork.misc",
}

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def model_from_url(url: str) -> str | None:
    """Runway asset URLs encode the model as the first path segment, e.g.
    https://<host>/gpt_image_2/<taskId>/<slug>_0.png -> gpt-image-2."""
    # buckets that are not generation models (uploads, processed captures)
    NON_MODEL = {"datasets", "media-processing", "uploads"}
    try:
        seg = urlparse(url).path.lstrip("/").split("/", 1)[0].replace("_", "-")
        return None if (not seg or seg in NON_MODEL) else seg
    except Exception:
        return None

def find_asset(payload: dict | list, task_id: str | None) -> dict | None:
    """Accept a single asset object, a list of them, or the full list_recent {'assets':[...]}."""
    if isinstance(payload, dict) and "assets" in payload:
        payload = payload["assets"]
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        if len(payload) == 1:
            return payload[0]
        if task_id:
            for a in payload:
                if a.get("taskId") == task_id or a.get("id") == task_id:
                    return a
        return None  # ambiguous: never silently default to the first asset
    return None

def build(args, asset: Path) -> dict:
    ext = asset.suffix.lower()
    rec = {
        "id": args.id or args.task_id or asset.stem,
        "file": asset.name,
        "project": args.project,
        "category": args.category,
        "subject": args.subject,
        "descriptor": args.descriptor,
        "version": args.version,
        "status": args.status,
        "structuralType": STRUCTURAL.get(ext, "digital.unknown"),
        "functionalType": FUNCTIONAL.get(args.category, "artwork.misc"),
        "createdAt": now_iso(),
        "generation": {
            "tool": args.tool, "model": args.model, "promptText": args.prompt,
            "seed": args.seed, "ratio": args.ratio, "taskId": args.task_id,
            "refs": args.ref or [],
        },
        # source (read-back lineage) and technical are filled by --enrich-json when available.
        "source": {"assetId": None, "parentAssetGroupId": None,
                   "sourceAssetId": None, "isUserUpload": None},
        "technical": {"width": None, "height": None, "aspectRatio": None,
                      "fileSize": None, "mediaType": None, "ext": ext.lstrip(".")},
    }
    if args.ai_generated:
        rec["provenance"] = {
            "digitalSourceType": "trainedAlgorithmicMedia",
            "aiDisclosure": {"model": args.model, "humanOversightLevel": args.oversight},
        }
    return rec

def enrich(rec: dict, a: dict) -> dict:
    """Merge verified fields from a Runway list_recent asset object. Read-back never overwrites
    gen-time truth (full prompt, explicit model); it only fills what the filename/call cannot."""
    meta = a.get("metadata") or {}
    size = meta.get("size") or {}
    rec["technical"].update({
        "width": size.get("width"), "height": size.get("height"),
        "aspectRatio": meta.get("aspectRatio"),
        "fileSize": a.get("fileSize"), "mediaType": a.get("mediaType"),
        "ext": a.get("fileExtStandardized") or rec["technical"]["ext"],
    })
    rec["source"].update({
        "assetId": a.get("id"), "parentAssetGroupId": a.get("parentAssetGroupId"),
        "sourceAssetId": a.get("sourceAssetId"), "isUserUpload": a.get("isUserUpload"),
    })
    if a.get("createdAt"):  # prefer the real generation timestamp over now()
        rec["createdAt"] = a["createdAt"]
    if not rec["generation"].get("model") and not a.get("isUserUpload"):
        # only fill model if gen-time did not set it, and only for generated (not uploaded) assets
        rec["generation"]["model"] = model_from_url(a.get("url", "") or "")
        if rec.get("provenance"):
            rec["provenance"]["aiDisclosure"]["model"] = rec["generation"]["model"]
    if not rec["generation"].get("ratio"):
        rec["generation"]["ratio"] = meta.get("aspectRatio")
    return rec

def update_manifest(manifest: Path, rec: dict) -> int:
    data = []
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            data = []
    if not isinstance(data, list):
        data = []
    data = [e for e in data if e.get("file") != rec["file"]]  # replace prior entry
    data.append(rec)
    manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return len(data)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("asset")
    ap.add_argument("--project", required=True)
    ap.add_argument("--category", required=True,
                    choices=["char", "loc", "scene", "style", "sheet", "shot", "cut", "misc"])
    ap.add_argument("--subject", required=True)
    ap.add_argument("--descriptor", required=True)
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--status", default="work", choices=["work", "publish"])
    ap.add_argument("--tool", default="runway")
    ap.add_argument("--model", default=None)
    ap.add_argument("--prompt", default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--ratio", default=None)
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--ref", action="append", help="reference asset/task id (repeatable)")
    ap.add_argument("--id", default=None)
    ap.add_argument("--ai-generated", action="store_true",
                    help="add the C2PA-shaped provenance block (trainedAlgorithmicMedia)")
    ap.add_argument("--oversight", default="hitl",
                    help="humanOversightLevel for the AI disclosure (default hitl)")
    ap.add_argument("--enrich-json", default=None,
                    help="path to a Runway list_recent payload (asset object or full response) "
                         "to reconcile technical/lineage fields from, matched by --task-id")
    ap.add_argument("--manifest", default=None,
                    help="manifest path (default: _manifest.json beside the asset)")
    args = ap.parse_args()

    asset = Path(args.asset).expanduser()
    if not asset.exists():
        print(f"error: asset not found: {asset}", file=sys.stderr)
        return 1

    rec = build(args, asset)

    if args.enrich_json:
        ep = Path(args.enrich_json).expanduser()
        if not ep.exists():
            print(f"error: --enrich-json not found: {ep}", file=sys.stderr)
            return 1
        a = find_asset(json.loads(ep.read_text()), args.task_id)
        if a is None:
            print(f"error: no asset matching task {args.task_id} in {ep}", file=sys.stderr)
            return 1
        rec = enrich(rec, a)

    sidecar = asset.with_suffix(".json")
    sidecar.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")

    manifest = Path(args.manifest).expanduser() if args.manifest else asset.parent / "_manifest.json"
    count = update_manifest(manifest, rec)

    print(f"sidecar -> {sidecar}")
    print(f"manifest -> {manifest}  ({count} entries)")
    print(f"model={rec['generation']['model']} dims="
          f"{rec['technical']['width']}x{rec['technical']['height']} "
          f"group={rec['source']['parentAssetGroupId']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
