---
name: media-asset-naming
description: Name, file, and track AI-generated media (images, video, audio) to a human-readable convention backed by a machine-readable sidecar, so assets are recognizable at a glance and reliably retrievable by an agent when orchestrating them into downstream workflows. Grounded in film/VFX shot naming (Netflix, MovieLabs), the MovieLabs Ontology for Media Creation (metadata separated from essence; structural vs functional), work-vs-publish separation (ShotGrid, ftrack), and C2PA/EU AI Act provenance. Use when downloading or filing generated assets, designing or applying an asset naming convention, building a project media library, or pulling assets into a lip-sync / image-to-video / edit workflow. Triggers on "name this asset", "naming convention", "file this generation", "asset library", "how should I name this", "sidecar", "content credentials", "provenance", "grab the asset for the workflow", "version this render".
license: Copyright (c) 2026 Trending Society LLC. All rights reserved.
metadata:
  version: "0.8"
  maintainer: "Trending Society LLC"
allowed-tools: Read Bash Write
---

# Media Asset Naming

Generated media is only useful later if a human can recognize it at a glance and an agent can
retrieve it without guessing. That takes two artifacts per asset: a **human-readable filename**
(the address) and a **machine-readable sidecar** (the record). This skill defines both, the folder
model, and the provenance layer for published work.

Most generation tools take a prompt and return an auto-named asset, with no field for a name or
metadata. So naming and metadata are enforced when the asset is **downloaded and filed**, not at
generation. That download step is where this skill does its work.

## Gotchas

- **Naming happens on download, never at generation.** A skipped download step leaves an
  auto-named cloud asset nobody can find.
- **Organize the local copy.** Treat the generator's cloud library as read-only; rename, move and
  tag the files on disk.
- **Some generators expose no seed.** When `generation.seed` is `null`, reproducibility rests on
  model, full prompt and references.

## The name, a human-readable address

```
<project>_<category>_<subject>_<descriptor>_v##.<ext>
   WHERE     WHAT-KIND    WHO        WHICH-ONE    VERSION
```

`spring-launch_sheet_ava_master_v01.png` reads as *Spring Launch · a sheet · of Ava · the master · v1*.

- lowercase; `-` within a field, `_` between fields; parses by splitting on `_`.
- `category` is a controlled vocab: `char` · `loc` · `scene` · `style` · `sheet` · `shot` · `cut` · `misc`.
- `subject` names the entity so you always know *who*: the field that makes a name self-explanatory.
- `v##` is monotonic and zero-padded. **Never `final`.** The approved take is the highest number.

Full grammar, folder model, and the work-vs-publish gate: `references/conventions.md`.

Use named subject/descriptor fields, not numbered VFX coordinates (`067_0010_comp_NFX`); keep the
film discipline (underscore address, zero-pad, monotonic, controlled vocab, no "final"). Rationale:
`references/conventions.md`.

## The sidecar, a machine-readable record

The filename cannot hold the prompt, seed, model, reference ids, task id, or provenance. Those go
in a JSON sidecar with the same basename (`..._v01.png` -> `..._v01.json`). This is the MovieLabs
2030 principle (**separate an asset's metadata from its essence**), and it is what makes assets
*retrievable when orchestrating*: a workflow queries the sidecars/manifest by field, it never parses
filenames. It also enables reproducibility: pulling a prior shot's seed + model so the next matches.

Metadata has two halves: **gen-time truth** (full prompt, model, refs; from the agent's own call args, lossless) and **read-back reconciliation** (dimensions, aspect ratio, real timestamp, edit lineage; from the generator's API response). Reconciling from the API response means an asset is identified without opening the image. A brand kit is just a project (`project: brandkit`): same grammar, same sidecar, so every logo/palette/type asset is self-describing.

Schema, the read-back field inventory, the `_manifest.json`, and provenance: `references/sidecar-and-provenance.md`.

## Close the loop on every generation: download, name, record, file

When you generate media and the user wants it kept:

1. **Generate.** Capture the returned task id and asset URL.
2. **Download it** to disk.
3. **Name it** to `<project>_<category>_<subject>_<descriptor>_v##.<ext>`. You know the subject and
   descriptor because you wrote the prompt. Fill them in full.
4. **Write the sidecar.** Pass the saved API response as `--enrich-json` so technical and lineage
   fields come from the API, not the pixels:
   ```bash
   scripts/write-sidecar.py ASSET.png --project spring-launch --category sheet \
     --subject ava --descriptor master --version 1 --status work \
     --tool <generator> --model <model> --task-id <id> --prompt "..." \
     [--ref <id>] [--ai-generated] [--enrich-json response.json]
   ```
   It writes `ASSET.json` and updates the project `_manifest.json`. Gen-time args (full prompt,
   explicit model) win; `--enrich-json` only fills what they cannot.
5. **File it** into the project's staged folder (`01_refs` / `02_sheets` / `03_shots` / `04_cuts`).

## Retrieve assets by querying the manifest

When pulling an asset into a lip-sync / image-to-video / edit workflow:

1. **Query the manifest, not the filenames.** Filter `_manifest.json` by `project`, `functionalType`
   (or `category`), and `subject`.
2. **Prefer `status: publish`** over `work`: pull the approved asset, not a half-baked iteration.
3. **Read `generation.seed` and `generation.model`** to reproduce or match a prior shot, not just
   its pixels.
4. **Use `generation.taskId`** to re-fetch or edit the source through the generator when you need a
   fresh URL.

## Attach provenance to anything published

Public AI media needs machine-readable provenance: C2PA Content Credentials
(`digitalSourceType: trainedAlgorithmicMedia` + the `c2pa.ai-disclosure` assertion), required by
EU AI Act Article 50. A credential is a signed statement of *origin, not a verdict of truth*, and
platforms strip it; keep the local sidecar as the durable record. Detail:
`references/sidecar-and-provenance.md`.

## Validation

After `write-sidecar.py`, open the sidecar and the project `_manifest.json` and confirm the new
entry carries the asset's task id, model and full prompt. Stop when every filed asset has a sidecar
and a manifest row.

## Scripts

- `scripts/write-sidecar.py`: writes an asset's sidecar JSON and updates the project manifest.
  Execute, do not read.
