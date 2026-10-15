---
name: claim-check
description: Re-measures factual claims about local files instead of trusting recall. Use whenever a response is about to state a line count, file count, version, path, commit hash or date; when reviewing a draft or a past session for claims that were asserted rather than measured; and when a checker or reviewer disputes a claim about a file. Triggers on "how many lines", "how big is", "is that still accurate", "did you verify that", "check my claims", "was that measured", "fact-check this against the repo", "that number looks wrong", "does that file exist". Owns claims about the local filesystem only, and stays silent on anything it cannot resolve.
license: Copyright (c) 2026 Trending Society LLC. All rights reserved.
metadata:
  version: "0.3"
  maintainer: "Trending Society LLC"
allowed-tools: Read Bash
---

# Re-measure every claim about a local file before stating it

A number in a response is either a measurement or a guess, and prose cannot tell them apart. This
skill runs the command.

Scope is **claims about the local filesystem**. Claims about the outside world are out of scope.

## Gotchas

- **A clean exit covers line counts only.** The script says nothing about file counts, versions,
  commit hashes or paths, so those still need a command run by hand.
- **A bare file name can resolve under more than one root.** `CLAUDE.md` exists in `~/.claude` and
  in most repos. Name the file a verdict applies to; never call a claim false because the working
  directory holds a different file of the same name.
- **A number measured earlier in the turn goes stale when the file is edited.** Re-measure after
  the last edit, not before it.

## Run the checker on a file

```bash
python3 scripts/check_claims.py DRAFT.md
python3 scripts/check_claims.py DRAFT.md --json
```

Exit `0` means nothing was disproven and `1` means a claim was contradicted. Any other code
means the check could not run; the script's docstring lists the codes.

- `--roots DIR,DIR` adds search roots; `~/.claude` and the working directory are always tried.
- The script reads a file, so write the text out first when checking a response rather than a
  draft on disk.

## Never state a count, size, version, line number, path, or date that no command produced this turn

The script is the enforcement, not a reminder to be careful.

## Report nothing for a path that does not resolve

**A path that will not resolve produces no finding.** Not a warning, not an "unverified" note that
reads as a defect.

- Try every root; when nothing resolves, say nothing.
- A checker that argues with correct claims costs more than the errors it catches.

## Treat a number as stale when `file_mtime` is newer than `measured_at`

| Field | Answers |
|---|---|
| `ran_at` | When the check ran |
| `measured_at` | When this particular number was taken |
| `file_mtime` | When the file last changed |

When `file_mtime` is **newer** than `measured_at`, the number is stale even though it was correct
when taken: you measured a file, kept working, edited it, then quoted the old figure.

Format is `Sunday, August 16th, 9:54 a.m. PDT`, zone always named.

## Check line-count claims only; verify everything else by hand

The script checks **line-count claims only**. A narrow check that never false-positives is worth
more than a broad one that has to be argued with.

For every other claim (file counts, versions, commit hashes, paths), run the command and paste the
output.

## Validation

Run `check_claims.py` on the draft, fix each contradicted claim, and run it again. Stop when it
exits `0` and every non-line-count claim has a command output pasted beside it.

## Scripts

- `scripts/check_claims.py`: finds line-count claims in a text file and re-measures each one.
  Execute, do not read.

