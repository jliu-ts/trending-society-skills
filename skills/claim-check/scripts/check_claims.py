#!/usr/bin/env python3
"""Re-measure the file claims in a piece of text. Tier 1, no model call.

CLAUDE.md rule 1 says never state a count, size, version or path that did not come
from a command this turn. Rule 2 says resolve what a claim refers to before making
it. This script is the enforcement: it finds those claims and runs the command.

Claims are read from prose and from markdown tables. In a table, a column headed
Lines / LOC / Line count carries the number and the row's backticked path owns it;
a row with no such column falls back to the prose rule ("`path` ... N lines").

It only reports what it can PROVE wrong. A path it cannot resolve is silence, not a
finding, because the alternative is the failure this replaces -- a checker that
reads `~/.claude/CLAUDE.md` against the wrong repo root and declares it missing.

Usage:
    check_claims.py TEXT_FILE [--json] [--roots DIR,DIR]

Exit codes:
    0  nothing disproven
    1  at least one claim contradicted by a measurement
    2  bad invocation / unreadable file
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")

DEFAULT_ROOTS = [
    os.path.expanduser("~/.claude"),
    os.getcwd(),
]

# `path` in backticks, or a bare path with a slash. Trailing punctuation trimmed.
PATH_TOKEN = re.compile(r"`([^`\n]{2,120})`")
LOOKS_LIKE_PATH = re.compile(r"^[~./A-Za-z0-9_-][A-Za-z0-9_./~-]*$")

# "<path> ... 143 lines"  or  "143 lines ... <path>", within one sentence.
LINES_CLAIM = re.compile(r"(\d[\d,]*)\s*lines\b", re.I)

# Markdown tables: a pipe row, then a separator row of dashes/colons.
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP = re.compile(r"^\s*\|(\s*:?-{2,}:?\s*\|)+\s*$")
LINES_HEADER = re.compile(r"^(?:lines?|loc|line\s*count|lines?\s*of\s*code)$", re.I)
CELL_NUMBER = re.compile(r"^~?(\d[\d,]*)(?:\s*lines?)?$", re.I)


def _resolve(token, roots):
    """Return an existing path for a token, or None. Tries every root before giving up."""
    t = token.strip().rstrip(".,;:)")
    if not LOOKS_LIKE_PATH.match(t) or " " in t:
        return None
    if t.startswith("~"):
        t = os.path.expanduser(t)
    if os.path.isabs(t):
        return t if os.path.exists(t) else None
    for r in roots:
        p = os.path.join(r, t)
        if os.path.exists(p):
            return p
    return None


def _stamp(when=None):
    """Display format: Sunday, August 16th, 9:41 a.m. PDT. Zone always named."""
    d = when or datetime.now(PT)
    n = d.day
    suffix = "th" if 11 <= n <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    hour = d.strftime("%I").lstrip("0") or "12"
    return (f"{d:%A}, {d:%B} {n}{suffix}, {hour}:{d:%M} "
            f"{'a.m.' if d.hour < 12 else 'p.m.'} {d:%Z}")


def _mtime(path):
    """When the file last changed, so a stale measurement is visible as stale."""
    try:
        return _stamp(datetime.fromtimestamp(os.path.getmtime(path), PT))
    except OSError:
        return None


def _wc(path):
    try:
        out = subprocess.run(["/usr/bin/wc", "-l", path],
                             capture_output=True, text=True, timeout=10)
        return int(out.stdout.split()[0]) if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def _strip_code(text):
    return re.sub(r"```.*?```", " ", text, flags=re.S)       # code blocks are not claims


def _cells(line):
    """Split a pipe row into trimmed cells; `\\|` stays inside its cell."""
    body = line.strip().strip("|")
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", body)]


def tables(text):
    """Yield (headers, rows) for each markdown table outside code fences."""
    lines = _strip_code(text).splitlines()
    i = 0
    while i < len(lines) - 1:
        if TABLE_ROW.match(lines[i]) and TABLE_SEP.match(lines[i + 1]):
            headers = _cells(lines[i])
            rows, i = [], i + 2
            while i < len(lines) and TABLE_ROW.match(lines[i]):
                rows.append(_cells(lines[i]))
                i += 1
            yield headers, rows
        else:
            i += 1


def sentences(text):
    """Prose sentences. Table rows are excluded; tables() owns them."""
    prose = "\n".join(l for l in _strip_code(text).splitlines()
                      if not TABLE_ROW.match(l))
    return [s for s in re.split(r"(?<=[.!?\n])\s+", prose) if s.strip()]


def _finding(real, claimed, actual, sent):
    return {
        "kind": "line-count",
        "path": real,
        "claimed": claimed,
        "actual": actual,
        "sentence": re.sub(r"\s+", " ", sent).strip()[:160],
        "command": f"wc -l {real}",
        # The measurement's own age. A number is only evidence for the turn it
        # was taken in, so it travels with the time rather than being asserted.
        "measured_at": _stamp(),
        "file_mtime": _mtime(real),
    }


def _check(token, claimed, sent, roots):
    """Measure one (path token, claimed count) pair. None unless provably wrong."""
    real = _resolve(token, roots)
    if not real or not os.path.isfile(real):
        return None                            # unresolvable is silence, never a finding
    actual = _wc(real)
    if actual is None or actual == claimed:
        return None
    return _finding(real, claimed, actual, sent)


def _scan_prose(sent, roots):
    # Pair each number with its NEAREST path, not the first number with every
    # path. "`a.json` is 240 lines and `b.py` is 4000 lines" is two claims, and
    # crossing them reports a real file against someone else's number.
    paths = [(m.start(), m.group(1)) for m in PATH_TOKEN.finditer(sent)]
    if not paths:
        return
    for hit in LINES_CLAIM.finditer(sent):
        claimed = int(hit.group(1).replace(",", ""))
        # English puts the subject first -- "`path` is N lines" -- so the owning
        # path is the closest one BEFORE the number. Nearest-by-distance picks
        # the following path instead and attributes a number to the wrong file.
        before = [p for p in paths if p[0] < hit.start()]
        pos, token = (max(before, key=lambda p: p[0]) if before
                      else min(paths, key=lambda p: p[0] - hit.start()))
        f = _check(token, claimed, sent, roots)
        if f:
            yield f


def _scan_table(headers, rows, roots):
    col = next((i for i, h in enumerate(headers) if LINES_HEADER.match(h.strip("*` "))), None)
    for cells in rows:
        row_text = " | ".join(cells)
        # The row's path is its first backticked token; the number is in the
        # Lines column. A short row (fewer cells than headers) is skipped, not guessed.
        if col is not None and col < len(cells):
            m = CELL_NUMBER.match(cells[col].strip("*` "))
            tokens = [t.group(1) for c in cells for t in PATH_TOKEN.finditer(c)]
            resolved = next((t for t in tokens if _resolve(t, roots)), None)
            if m and resolved:
                f = _check(resolved, int(m.group(1).replace(",", "")), row_text, roots)
                if f:
                    yield f
                continue
        yield from _scan_prose(row_text, roots)   # no Lines column: "`path` ... N lines"


def scan(text, roots):
    findings = []
    for sent in sentences(text):
        findings.extend(_scan_prose(sent, roots))
    for headers, rows in tables(text):
        findings.extend(_scan_table(headers, rows, roots))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text_file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--roots", default="")
    args = ap.parse_args()

    roots = [r for r in args.roots.split(",") if r] + DEFAULT_ROOTS
    path = Path(args.text_file)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2
    try:
        findings = scan(path.read_text(encoding="utf-8"), roots)
    except UnicodeDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    ran_at = _stamp()
    if args.json:
        print(json.dumps({"pass": not findings, "ran_at": ran_at,
                          "findings": findings}, indent=2))
        return 1 if findings else 0

    if not findings:
        print(f"CLEAN  {ran_at}  no file claim contradicted by measurement")
        return 0
    print(f"FLAGGED  {ran_at}  {len(findings)} claim(s) contradicted")
    for f in findings:
        print(f"\n  [{f['kind']}] {f['path']}")
        print(f"    claimed {f['claimed']}, actual {f['actual']}  ({f['command']})")
        print(f"    measured {f['measured_at']}  ·  file last changed {f['file_mtime']}")
        print(f"    in: {f['sentence']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
