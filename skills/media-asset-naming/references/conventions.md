# Naming convention, the human-readable address

## Contents
- [The grammar](#the-grammar)
- [The fields](#the-fields)
- [Controlled category vocab](#controlled-category-vocab)
- [Versioning rules](#versioning-rules)
- [Folders and the work-vs-publish gate](#folders-and-the-work-vs-publish-gate)
- [Examples](#examples)
- [Why named fields, not numbered VFX coordinates](#why-named-fields-not-numbered-vfx-coordinates)
- [Grounding](#grounding)

## The grammar

```
<project>_<category>_<subject>_<descriptor>_v##.<ext>
   WHERE     WHAT-KIND    WHO        WHICH-ONE    VERSION
```

- **lowercase, no spaces.** `-` within a field, `_` between fields, so a name parses
  without knowing the schema: `spring-launch | sheet | ava | master | v01`.
- The filename is an **address, not a label**: humans read it at a glance, and `glob`/scripts
  parse it by splitting on `_`. Everything a filename cannot hold (prompt, seed, model, task id,
  provenance) goes in the sidecar, see `sidecar-and-provenance.md`.

## The fields

| Field | Meaning | Form | Example |
|---|---|---|---|
| `project` | The production / show | kebab | `spring-launch`, `skincare` |
| `category` | Functional class (controlled vocab) | one token | `sheet`, `char`, `shot` |
| `subject` | Who or what it is (the entity) | kebab | `ava`, `ava`, `fox` |
| `descriptor` | Which one, angle, beat, refinement | kebab | `master`, `front-34`, `bus-stop` |
| `v##` | Version | zero-padded, `v`-prefixed | `v01`, `v12` |

`subject` is the field that makes a name self-explanatory, you always know *who* the asset is
of. On bulk imports where the source filename does not reveal the subject, leave it generic
(`subject` = the category's default) until a vision/human tag pass fills it; the orchestration
path (generating through the MCP) always knows the subject, so it names in full.

## Controlled category vocab

One of these; do not invent new categories without adding them here:

`char` · `loc` · `scene` · `style` · `sheet` · `shot` · `cut` · `misc`

These map to MovieLabs Ontology for Media Creation *functional* types (how the asset is used):
`char`/`loc` ≈ `artwork.characterDesign`/`artwork.environment`, `sheet` ≈ reference turnaround,
`shot`/`cut` ≈ `video`/edited output. The file *extension* carries the *structural* type
(`.png` = `digital.image`, `.mp4` = `digital.movingImage`).

## Versioning rules

- **Monotonic, zero-padded, `v`-prefixed:** `v01`, `v02`, … Never `final`, `final-real`,
  `FINAL_v2`. The approved take is simply the **highest number**, history stays traceable.
- Bump the version for every new take of the *same* thing (same project/category/subject/descriptor).
- A different angle or beat is a new **descriptor**, not a new version.

## Folders and the work-vs-publish gate

Per project under `<library>/projects/<name>/`:

```
01_refs/    char, loc, scene, style     (inputs / references)
02_sheets/  master + contact sheets
03_shots/   individual generated shots
04_cuts/    assembled cuts              (deliverables)
```

Plus at the Runway root: `_inbox/` (unsorted, awaiting a project), `_archive/` (dupes, superseded).

**Work vs publish** (the studio discipline this half-implements): iterations are *work*; approved,
named, reusable assets are *publish*. Treat `_inbox/` + low versions as work, and a filed asset in
its staged folder with a sidecar marked `status: publish` as the deliverable. A workflow should
pull *publish* assets, not half-baked work versions.

## Examples

- `spring-launch_sheet_ava_master_v01.png`: Spring Launch · a sheet · of Ava · the master · v1
- `spring-launch_shot_ava_bus-stop-es-lipsync_v03.mp4`: a shot · of Ava · bus-stop Spanish lip-sync · v3
- `skincare_char_ava_front-34-smile_v02.png`: Skincare · a character ref · of Ava · front ¾ smiling · v2
- `spring-launch_cut_trailer_all_v06.mp4`: an assembled cut · the trailer · v6

## Why named fields, not numbered VFX coordinates

Film uses `SHOW_SEQ_SHOT_TASK_VENDOR_vNNN` (e.g. `AGM_104_TCC_067_0010_comp_NFX_v001`) because
hundreds of vendors and thousands of shots need collision-proof numeric coordinates. A solo
creative needs **recognition**, not coordinates: `ava_master` tells you what it is; `067_0010`
makes you look it up. So this convention keeps the film *discipline* (underscore address, zero-pad,
monotonic version, controlled vocab, no "final") but uses **named** subject/descriptor fields.

## Grounding

- Underscore address, `vNNN` monotonic, "final" banned, controlled task vocab, number-by-10s:
  Netflix VFX Shot & Version Naming; PostMicroTools shot-namer; MovieLabs/ETC Image Sequence Naming.
- Functional vs structural separation, metadata separated from essence: MovieLabs Ontology for
  Media Creation (2030 Vision).
- Work-vs-publish namespaces, Asset -> AssetVersion -> Components: ShotGrid/Flow Toolkit, ftrack.
