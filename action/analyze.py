#!/usr/bin/env python3
"""Analyze Checkov Terraform findings via Groq and write structured results."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import click
from groq import Groq


SYSTEM_PROMPT = (
    "You are a DevOps engineer explaining infrastructure security findings "
    "to a junior engineer. Be specific, be practical, never be vague. "
    "Respond ONLY in valid JSON, no markdown, no preamble."
)

PROVIDER_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}

OUTPUT_FILE = "opspilot-results.json"


def _chat(provider: str, api_key: str, user_prompt: str) -> str:
    """Call the chosen LLM provider and return the raw text response."""
    if provider == "groq":
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=PROVIDER_MODELS["groq"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return (completion.choices[0].message.content or "").strip()

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=PROVIDER_MODELS["openai"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return (completion.choices[0].message.content or "").strip()

    if provider == "anthropic":
        import anthropic as anthropic_sdk
        client = anthropic_sdk.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=PROVIDER_MODELS["anthropic"],
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.2,
        )
        return (message.content[0].text or "").strip()

    raise ValueError(f"Unknown provider: {provider!r}. Choose groq, openai, or anthropic.")


def format_code_block(code_block: Any) -> str:
    """Turn Checkov code_block (list of [line, text] or string) into a single string."""
    if code_block is None:
        return ""
    if isinstance(code_block, str):
        return code_block
    if isinstance(code_block, list):
        parts: list[str] = []
        for item in code_block:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                _, line_text = item[0], item[1]
                parts.append(str(line_text))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(code_block)


def _matching_brace_end(text: str, open_brace_idx: int) -> int | None:
    """Return index of the `}` that closes the `{` at open_brace_idx."""
    depth = 0
    for i in range(open_brace_idx, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def extract_resource_hcl_from_tf(tf_text: str, resource_addr: str) -> str | None:
    """
    Best-effort extract `resource "type" "name" { ... }` for addresses like aws_s3_bucket.ml_data.
    """
    if "." not in resource_addr:
        return None
    res_type, res_name = resource_addr.split(".", 1)
    pattern = rf'resource\s+"{re.escape(res_type)}"\s+"{re.escape(res_name)}"\s*\{{'
    m = re.search(pattern, tf_text, flags=re.MULTILINE)
    if not m:
        return None
    open_idx = m.end() - 1
    close_idx = _matching_brace_end(tf_text, open_idx)
    if close_idx is None:
        return None
    return tf_text[m.start() : close_idx + 1].strip()


def resolve_checkov_json_path(checkov_output: str | None, tf_file: str | None) -> str | None:
    """
    If --checkov-output is set, only that path is used (no silent fallback to other JSON files).

    If it is omitted, try ./findings.json, then findings.json next to --tf-file.
    """
    if checkov_output:
        return checkov_output if os.path.isfile(checkov_output) else None
    cwd_findings = os.path.abspath("findings.json")
    if os.path.isfile(cwd_findings):
        return cwd_findings
    if tf_file and os.path.isfile(tf_file):
        sibling = os.path.join(os.path.dirname(os.path.abspath(tf_file)), "findings.json")
        if os.path.isfile(sibling):
            return sibling
    return None


def load_tf_fallback_text(tf_path: str | None, finding_file_path: str | None) -> str | None:
    """Prefer finding's file_path if readable; else use explicit --tf-file."""
    candidates: list[str] = []
    if finding_file_path:
        candidates.append(finding_file_path)
    if tf_path:
        candidates.append(tf_path)
    for path in candidates:
        if not path:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            continue
    return None


def resolve_code_for_finding(
    finding: dict[str, Any],
    tf_file: str | None,
) -> str:
    raw = format_code_block(finding.get("code_block"))
    if raw:
        return raw
    resource = str(finding.get("resource") or "")
    tf_text = load_tf_fallback_text(tf_path=tf_file, finding_file_path=finding.get("file_path"))
    if tf_text and resource:
        extracted = extract_resource_hcl_from_tf(tf_text, resource)
        if extracted:
            return extracted
    return ""


def strip_markdown_json_fence(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.splitlines()
    if not lines:
        return t
    # drop opening fence ``` or ```json
    lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_llm_json(content: str) -> dict[str, Any]:
    cleaned = strip_markdown_json_fence(content)
    return json.loads(cleaned)


def analyze_finding(
    provider: str,
    api_key: str,
    finding: dict[str, Any],
    tf_file: str | None,
) -> dict[str, Any]:
    check_id = str(finding.get("check_id") or "")
    check_name = str(finding.get("check_name") or "")
    resource = str(finding.get("resource") or "")
    file_path = finding.get("file_path")
    code_block = resolve_code_for_finding(finding, tf_file)

    user_prompt = f"""Checkov flagged this Terraform resource:

Check: {check_id} — {check_name}
Resource: {resource}
Code:
{code_block}

Respond ONLY in valid JSON, no markdown, no preamble:
{{
  "check_id": "{check_id}",
  "resource": "{resource}",
  "severity": "critical|warning|info (pick one)",
  "explanation": "1-2 sentences: what is wrong and the concrete risk",
  "why_it_matters": "1 sentence: what an attacker or accident could do if this hits production",
  "fix_code": "EXACT Terraform code only. If referencing a secret, use data.aws_secretsmanager_secret_version.name.secret_string. If adding a new resource, show the resource block. Do not invent syntax. Do not include explanations in this field.",
  "fix_description": "1 sentence: what this fix does"
}}

Common fixes:
- Hardcoded secret → url = data.aws_secretsmanager_secret_version.slack_token.secret_string
- Public S3 bucket → add resource "aws_s3_bucket_public_access_block" with block_public_acls = true
- Missing encryption → add kms_key_id = aws_kms_key.ebs.arn
- Open security group → cidr_blocks = ["10.0.0.0/8"] instead of ["0.0.0.0/0"]

Be precise. Be literal. Do not guess syntax."""
    raw_content = _chat(provider, api_key, user_prompt)
    parsed = parse_llm_json(raw_content)
    return {
        "check_id": check_id,
        "check_name": check_name,
        "resource": resource,
        "file_path": file_path,
        "code_block": code_block,
        **{k: parsed.get(k) for k in ("severity", "explanation", "why_it_matters", "fix_code", "fix_description")},
    }


def load_checkov_findings(checkov_path: str) -> list[dict[str, Any]]:
    with open(checkov_path, encoding="utf-8") as f:
        data = json.load(f)
    # checkov 3.x returns a list when multiple --file flags are used
    if isinstance(data, list):
        data = data[0] if data else {}
    results = data.get("results") or {}
    failed = results.get("failed_checks") or []
    if not isinstance(failed, list):
        return []
    return [x for x in failed if isinstance(x, dict)]


def print_summary_table(rows: list[dict[str, Any]]) -> None:
    headers = ("resource", "check_id", "severity", "explanation")
    cells: list[list[str]] = [list(headers)]
    for r in rows:
        expl = str(r.get("explanation") or "").replace("\n", " ").strip()
        cells.append(
            [
                str(r.get("resource") or ""),
                str(r.get("check_id") or ""),
                str(r.get("severity") or ""),
                expl,
            ]
        )
    widths = [max(len(row[i]) for row in cells) for i in range(4)]
    sep = " | "
    for idx, row in enumerate(cells):
        line = sep.join(row[i].ljust(widths[i]) for i in range(4))
        click.echo(line)
        if idx == 0:
            click.echo(sep.join("-" * widths[i] for i in range(4)))


@click.command()
@click.option(
    "--checkov-output",
    "checkov_output",
    type=click.Path(dir_okay=False, path_type=str),
    default=None,
    help="Path to Checkov JSON output (contains results.failed_checks).",
)
@click.option(
    "--tf-file",
    "tf_file",
    type=click.Path(dir_okay=False, path_type=str),
    default=None,
    help="Fallback Terraform file to enrich missing code_block excerpts.",
)
def main(checkov_output: str | None, tf_file: str | None) -> None:
    provider = (os.environ.get("INPUT_LLM_PROVIDER") or "groq").strip().lower()

    key_env = {
        "groq": "GROQ_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    if provider not in key_env:
        click.echo(
            f"error: unknown llm-provider {provider!r}. Choose groq, openai, or anthropic.",
            err=True,
        )
        raise SystemExit(1)

    api_key = os.environ.get(key_env[provider]) or ""
    if not api_key:
        click.echo(
            f"error: {key_env[provider]} is not set (required for provider={provider}).",
            err=True,
        )
        raise SystemExit(1)

    json_path = resolve_checkov_json_path(checkov_output, tf_file)
    if not json_path:
        if checkov_output:
            click.echo(f"error: --checkov-output file not found: {checkov_output}", err=True)
        else:
            click.echo(
                "error: could not find Checkov JSON. Pass --checkov-output, or place findings.json "
                "in the current directory (or next to --tf-file). "
                "Generate JSON with Checkov, for example: "
                "checkov --file main.tf -o json > findings.json",
                err=True,
            )
        raise SystemExit(1)

    findings = load_checkov_findings(json_path)
    click.echo(f"Provider: {provider} / Model: {PROVIDER_MODELS[provider]}")

    results: list[dict[str, Any]] = []
    for finding in findings:
        try:
            row = analyze_finding(provider, api_key, finding, tf_file)
            results.append(row)
        except json.JSONDecodeError as e:
            click.echo(
                f"warning: could not parse JSON from model for "
                f"{finding.get('check_id')} / {finding.get('resource')}: {e}. Skipping.",
                err=True,
            )
            continue
        except Exception as e:  # noqa: BLE001 - surface API/SDK errors per finding
            click.echo(
                f"warning: {provider} API error for {finding.get('check_id')} / "
                f"{finding.get('resource')}: {e}. Skipping.",
                err=True,
            )
            continue

    out_path = OUTPUT_FILE
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        f.write("\n")

    click.echo(f"Wrote {len(results)} result(s) to {out_path}")
    if results:
        print_summary_table(results)


if __name__ == "__main__":
    main()
