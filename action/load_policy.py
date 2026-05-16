#!/usr/bin/env python3
"""Load .opspilot.yml team policy from the workspace root."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import click


POLICY_FILENAME = ".opspilot.yml"


@dataclass
class PolicyConfig:
    rules: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)


def load_policy(workspace: str | None = None) -> PolicyConfig:
    """Read .opspilot.yml from workspace root. Returns empty config on any failure."""
    ws = workspace or os.environ.get("GITHUB_WORKSPACE") or os.getcwd()
    path = os.path.join(ws, POLICY_FILENAME)

    if not os.path.isfile(path):
        return PolicyConfig()

    try:
        import yaml  # bundled with checkov
    except ImportError:
        click.echo("warning: PyYAML not available; skipping policy file.", err=True)
        return PolicyConfig()

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        click.echo(f"warning: could not parse {POLICY_FILENAME}: {e}. Using empty policy.", err=True)
        return PolicyConfig()

    if not isinstance(data, dict):
        click.echo(f"warning: {POLICY_FILENAME} is not a YAML mapping. Using empty policy.", err=True)
        return PolicyConfig()

    rules = data.get("rules") or []
    ignore = data.get("ignore") or []

    if not isinstance(rules, list):
        click.echo(f"warning: {POLICY_FILENAME}: 'rules' must be a list. Ignoring it.", err=True)
        rules = []
    if not isinstance(ignore, list):
        click.echo(f"warning: {POLICY_FILENAME}: 'ignore' must be a list. Ignoring it.", err=True)
        ignore = []

    return PolicyConfig(
        rules=[str(r).strip() for r in rules if r],
        ignore=[str(i).strip() for i in ignore if i],
    )
