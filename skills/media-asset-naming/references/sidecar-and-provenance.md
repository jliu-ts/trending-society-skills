# The sidecar and provenance, the machine-readable record

## Contents
- [The sidecar is the machine index](#the-sidecar-is-the-machine-index)
- [Two halves: gen-time truth and read-back reconciliation](#two-halves-gen-time-truth-and-read-back-reconciliation)
- [Sidecar schema](#sidecar-schema)
- [What read-back actually returns](#what-read-back-actually-returns)
- [The project manifest](#the-project-manifest)
- [Provenance for published assets](#provenance-for-published-assets)
- [Grounding](#grounding)

## The sidecar is the machine index

The filename is the human index; the **sidecar** is the machine index. Together they mean neither a
human nor an agent ever re-opens the image to know what it is, you read the name, the agent reads
the sidecar. It holds everything a filename cannot: the prompt, model, references, task id,
dimensions, lineage, and provenance. This is the MovieLabs 2030 principle, **separate an asset's
metadata from its essence**, and it is what makes assets *retrievable when orchestrating*: a
workflow queries the sidecars/manifest by field, it never parses filenames or re-analyzes pixels.
It also enables reproducibility, pulling a prior shot's model + prompt so the next matches.

## Two halves: gen-time truth and read-back reconciliation

Metadata comes from two sources, and the split is deliberate:

1. **Gen-time truth (lossless).** The full `promptText`, `model`, `ratio`, and reference lineage
   come from the agent's own `generate_image` call args. The **full prompt only exists here**, the
   read-back API truncates it. Capture at generation time whenever possible.
2. **Read-back reconciliation.** For an already-generated asset (or to enrich a fresh one), the
   Runway `list_recent` payload supplies the verified technical + lineage fields the API actually
   returns. `scripts/write-sidecar.py --enrich-json <payload>` merges them, matched by task id.
   **Read-back never overwrites gen-time truth**: it only fills what the call/filename cannot.

The agent fetches the `list_recent` payload (it has MCP access); the script stays deterministic and
parses that payload (it does not). This reconciles a download **without spending vision tokens on
the image**: the metadata is read from the API, not the pixels.

## Sidecar schema

One JSON per asset, same basename with a `.json` extension
(`spring-launch_sheet_ava_master_v01.png` -> `spring-launch_sheet_ava_master_v01.json`):

```json
{
  "id": "runway-task-id-or-uuid",
  "file": "spring-launch_char_ava_focused_v01.png",
  "project": "spring-launch",
  "category": "char",
  "subject": "ava",
  "descriptor": "focused",
  "version": 1,
  "status": "publish",
  "structuralType": "digital.image",
  "functionalType": "artwork.characterDesign",
  "createdAt": "2026-09-15T02:02:30.040Z",
  "generation": {
    "tool": "runway",
    "model": "gpt-image-2",
    "promptText": "Create a single front-facing studio portrait ...",
    "seed": null,
    "ratio": "4:3",
    "taskId": "16f19eed-f567-47f4-bcbc-17fa286794a8",
    "refs": ["<taskId or asset id of each reference image>"]
  },
  "source": {
    "assetId": "e2c68211-7f35-48a3-a398-6d24651288db",
    "parentAssetGroupId": "e7f7e2b3-3aba-4018-9c35-c5db812cc9b7",
    "sourceAssetId": null,
    "isUserUpload": false
  },
  "technical": {
    "width": 2560, "height": 1920, "aspectRatio": "4:3",
    "fileSize": 6994693, "mediaType": "image", "ext": "png"
  },
  "provenance": {
    "digitalSourceType": "trainedAlgorithmicMedia",
    "aiDisclosure": { "model": "gpt-image-2", "humanOversightLevel": "hitl" }
  }
}
```

- `status`: `work` (iteration) or `publish` (approved, reusable). Workflows pull `publish`.
- `structuralType`/`functionalType`: OMC axes, *what it is* vs *how it is used*.
- `generation`: gen-time truth + reproducibility payload. `seed` is `null` because Runway's image
  models do not expose one (verified against the `generate_image` schema, there is no seed param).
- `source`: read-back lineage. `parentAssetGroupId` stitches a batch/turnaround back into one set;
  `sourceAssetId` links an edit to its parent.
- `technical`: dimensions, aspect ratio, size, filled from the read-back payload.

## What read-back actually returns

Verified against a live `list_recent` call on the workspace. Per asset, the API returns:

| Field | In payload | Notes |
|---|---|---|
| model | via `url` path segment (`/gpt_image_2/` -> `gpt-image-2`) | not a named field; parsed from the URL |
| full prompt | NO | `name` + URL slug carry only a ~60-90 char truncation |
| seed | NO | not exposed by the models |
| dimensions, aspectRatio | `metadata.size`, `metadata.aspectRatio` | e.g. 2560x1920, "4:3" |
| createdAt | yes (real timestamp) | prefer over the local now() |
| assetId, taskId | yes | stable handles to re-fetch |
| parentAssetGroupId | yes | batch/turnaround grouping |
| sourceAssetId | yes (null unless an edit) | edit lineage |
| isUserUpload | yes | generated vs uploaded |
| fileSize, ext, mediaType, favorite, tags | yes | technical + user flags |

The developer API (`get_task` = `GET /v1/tasks/:id`) is scoped to the *developer* workspace; assets
generated in the *marketing* workspace are not visible there. Use `list_recent` for those.

## The project manifest

A per-project `_manifest.json` (array of sidecar objects) is the query surface. "Give me the
published front-facing clone frame for spring-launch" is a filter over the manifest, not a directory
scan. `write-sidecar.py` updates it on each write (idempotent, keyed by basename).

## Provenance for published assets

For anything shipped **publicly**, attach C2PA Content Credentials and keep the sidecar as the
durable copy:

- **What to assert:** a `c2pa.actions` assertion with an inception action carrying
  `digitalSourceType: trainedAlgorithmicMedia`, plus the `c2pa.ai-disclosure` assertion (model,
  `humanOversightLevel`) introduced in C2PA v2.4.
- **Why:** the EU AI Act Article 50 requires AI-generated media to be marked in a machine-readable
  way, and it is now applicable.
- **The honest caveat (do not overclaim):** a Content Credential is a cryptographically signed
  statement of *who did what*, **not a verdict that the content is true or real**, and its absence
  proves nothing. Platforms routinely strip the manifest on upload. So the credential is the public
  signal; the **local sidecar is the durable record** you actually rely on.

## Grounding

- Metadata separated from essence; structural vs functional: MovieLabs Ontology for Media Creation.
- C2PA v2.4 assertions (`c2pa.actions`, `digitalSourceType`, `c2pa.ai-disclosure`): C2PA Technical
  Specification 2.4 and the C2PA synthetic-content white paper.
- EU AI Act Article 50 machine-readable marking.
- "Credential is a statement, not a verdict; stripped by platforms": C2PA's own guidance.
- Read-back field inventory: live `list_recent` call against the workspace.
