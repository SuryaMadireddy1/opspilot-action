#!/usr/bin/env python3
"""Build PR markdown from opspilot-results.json (stdin or path arg)."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def _bucket(severity: str) -> str:
    s = (severity or "").strip().lower()
    if s == "critical":
        return "critical"
    if s in ("high", "warning"):
        return "high"
    if s == "info":
        return "info"
    return "other"


def _escape_fence(text: str) -> str:
    """Avoid breaking triple-backtick fences."""
    if not text:
        return ""
    t = text.replace("\r\n", "\n")
    if "```" in t:
        return t.replace("```", "``\u200b`")
    return t


def _fmt_finding(row: dict[str, Any]) -> str:
    check_id = str(row.get("check_id") or "").strip()
    check_name = str(row.get("check_name") or "").strip()
    resource = str(row.get("resource") or "").strip()
    explanation = str(row.get("explanation") or "").strip()
    why = str(row.get("why_it_matters") or "").strip()
    fix_code = str(row.get("fix_code") or "").strip()
    fix_desc = str(row.get("fix_description") or "").strip()

    title = f"**{check_id}: {check_name}** (`{resource}`)" if check_name else f"**{check_id}** (`{resource}`)"
    lines = [title, "", explanation]
    if why:
        lines += ["", f"**Why it matters:** {why}"]
    if fix_desc:
        lines += ["", f"**Fix:** {fix_desc}"]
    if fix_code:
        lines += ["", "**Fix (HCL)**", "", "```hcl", _escape_fence(fix_code).rstrip(), "```"]
    return "\n".join(lines).strip()


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: format_comment.py <opspilot-results.json>", file=sys.stderr)
        raise SystemExit(2)
    raw = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    rows: list[dict[str, Any]] = json.loads(raw) if raw else []
    if not isinstance(rows, list):
        rows = []

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            continue
        buckets[_bucket(str(row.get("severity") or ""))].append(row)

    crit = buckets["critical"]
    high = buckets["high"]
    info = buckets["info"]
    other = buckets["other"]

    total = len(rows)
    y, z, w, o = len(crit), len(high), len(info), len(other)
    parts: list[str] = []
    parts.append("## OpsPilot Review 🤖")
    parts.append("")
    if w == 0 and o == 0:
        summary = f"**Summary:** {total} finding(s) in this PR ({y} critical, {z} high)"
    else:
        summary = f"**Summary:** {total} finding(s) in this PR ({y} critical, {z} high, {w} info"
        if o:
            summary += f", {o} other"
        summary += ")"
    parts.append(summary)
    parts.append("")

    def section(emoji: str, title: str, items: list[dict[str, Any]], open_default: bool) -> None:
        if not items:
            return
        open_attr = " open" if open_default else ""
        parts.append(f"<details{open_attr}>")
        parts.append(f"<summary><strong>{emoji} {title} ({len(items)})</strong></summary>")
        parts.append("")
        for idx, it in enumerate(items):
            parts.append(_fmt_finding(it))
            if idx != len(items) - 1:
                parts.append("")
                parts.append("---")
                parts.append("")
        parts.append("")
        parts.append("</details>")
        parts.append("")

    section("🔴", "Critical", crit, True)
    section("🟡", "High", high, False)
    section("🔵", "Info", info, False)
    section("⚪", "Other", other, False)

    if total == 0:
        parts.append("_No Terraform security findings from Checkov for changed `.tf` files in this PR._")
        parts.append("")

    parts.append("---")
    parts.append("")
    parts.append("OpsPilot is solo-maintained. See docs/limitations.md")

    sys.stdout.write("\n".join(parts).rstrip() + "\n")


if __name__ == "__main__":
    main()
