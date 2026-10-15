# Trending Society skills

Agent skills from Trending Society, written for Claude Code and other agents that load `SKILL.md` files.

| Skill | What it does |
| --- | --- |
| [claim-check](skills/claim-check/SKILL.md) | Re-measures line-count claims about local files before an agent states them, and flags any claim a measurement contradicts. |
| [media-asset-naming](skills/media-asset-naming/SKILL.md) | Names and files AI-generated images, video and audio to a film-style convention, with a JSON sidecar per asset that records the prompt, model and provenance. |

## Use a skill

Copy a skill's folder into your agent's skills directory, for example `~/.claude/skills/claim-check/`.

Run the claim checker on a draft:

```bash
python3 skills/claim-check/scripts/check_claims.py DRAFT.md
```

It exits `0` when no claim is contradicted and `1` when one is.

Each skill has an `evals/` folder with the test cases it is checked against.

## License

Copyright (c) 2026 Trending Society LLC. All rights reserved. See [LICENSE](LICENSE).
