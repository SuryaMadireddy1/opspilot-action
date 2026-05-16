#!/usr/bin/env python3
"""Parse GitHub PR patch fields into per-file added-line-number sets.

Input:  pr-diff.json  — [{filename, patch}, ...]  (from GitHub PR files API)
Output: added-lines.json — {filename: [line, ...], ...}  (1-indexed new-file lines)
"""

from __future__ import annotations

import json
import re
from typing import Any

import click

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_patch(patch: str | None) -> list[int]:
    """Return sorted list of added line numbers (new-file coords) from a unified diff patch."""
    if not patch:
        return []
    added: list[int] = []
    current = 0
    for line in patch.splitlines():
        m = HUNK_RE.match(line)
        if m:
            current = int(m.group(1))
            continue
        if line.startswith("+"):
            added.append(current)
            current += 1
        elif line.startswith("-"):
            pass  # removed line — don't advance new-file counter
        else:
            current += 1  # context line
    return added


@click.command()
@click.option("--diff", "diff_path", required=True, type=click.Path(exists=True, dir_okay=False), help="Path to pr-diff.json")
@click.option("--out", "out_path", required=True, type=click.Path(dir_okay=False), help="Path to write added-lines.json")
def main(diff_path: str, out_path: str) -> None:
    with open(diff_path, encoding="utf-8") as f:
        files: list[dict[str, Any]] = json.load(f)

    result: dict[str, list[int]] = {}
    for entry in files:
        filename = entry.get("filename", "")
        added = parse_patch(entry.get("patch"))
        result[filename] = added
        click.echo(f"  {filename}: {len(added)} added line(s)")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    click.echo(f"Diff parsed: {len(result)} file(s) → {out_path}")


if __name__ == "__main__":
    main()
