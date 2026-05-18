# OpsPilot

> Checkov tells you what's wrong. OpsPilot tells you why it matters and how to fix it.

## What it does

OpsPilot runs [Checkov](https://www.checkov.io/) on the `.tf` files changed in your PR, sends each finding to an LLM, and posts a comment explaining the risk in plain English with exact fix code. Every finding gets a severity, a one-sentence explanation of what could go wrong in production, and a drop-in HCL snippet.

```markdown
## OpsPilot Review 🤖

**Summary:** 3 finding(s) in this PR (1 critical, 2 high)

<details open>
<summary><strong>🔴 Critical (1)</strong></summary>

**CKV_AWS_RDS_2: Ensure that RDS database has IAM Authentication enabled** (`aws_db_instance.prod`)

Hardcoded password in plain text — any engineer with repo access has
production database credentials.

**Why it matters:** An attacker who reads your source or CI logs owns your database.

**Fix:** Use AWS Secrets Manager and reference the secret at runtime.

**Fix (HCL)**

```hcl
password = data.aws_secretsmanager_secret_version.db_pass.secret_string
```

</details>
```

## Install

Add this to `.github/workflows/opspilot.yml`:

```yaml
name: OpsPilot
on: [pull_request]
permissions:
  pull-requests: write
  contents: read
jobs:
  opspilot:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: SuryaMadireddy1/opspilot-action/action@v1.3.0
        with:
          groq-api-key: ${{ secrets.GROQ_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ github.token }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
```

Add `GROQ_API_KEY` to your repo secrets (Settings → Secrets → Actions). Get a free key at [console.groq.com](https://console.groq.com).

See [`examples/opspilot.yml`](examples/opspilot.yml) for a ready-to-copy workflow file.

## Configuration

All inputs are optional. Pass them under `with:` in your workflow.

| Input | Default | Description |
|---|---|---|
| `llm-provider` | `groq` | LLM backend: `groq`, `openai`, or `anthropic` |
| `groq-api-key` | — | Required when `llm-provider` is `groq` |
| `openai-api-key` | — | Required when `llm-provider` is `openai` |
| `anthropic-api-key` | — | Required when `llm-provider` is `anthropic` |
| `fail-on-findings` | `false` | Set to `true` to exit non-zero if any critical finding is found, blocking the merge |
| `checkov-severity` | _(empty)_ | Pipe-separated Checkov severity filter (e.g. `critical\|high`). Leave empty to run all checks — most Checkov checks have `null` severity and would be excluded if this is set |

### Switching LLM providers

```yaml
- uses: SuryaMadireddy1/opspilot-action/action@v1.3.0
  with:
    llm-provider: openai
    openai-api-key: ${{ secrets.OPENAI_API_KEY }}
  env:
    GITHUB_TOKEN: ${{ github.token }}
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### Blocking merges on critical findings

```yaml
- uses: SuryaMadireddy1/opspilot-action/action@v1.3.0
  with:
    groq-api-key: ${{ secrets.GROQ_API_KEY }}
    fail-on-findings: 'true'
  env:
    GITHUB_TOKEN: ${{ github.token }}
    GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
```

### Team policy file (`.opspilot.yml`)

Place an `.opspilot.yml` at the root of your repo to customize OpsPilot behavior without changing the workflow:

```yaml
# Custom rules — appended to the LLM system prompt.
# OpsPilot flags violations it detects in each finding.
rules:
  - "All RDS instances must have deletion_protection = true"
  - "S3 buckets must never use acl = public-read"
  - "All resources must have a cost-center tag"

# Checkov check IDs to skip entirely (no LLM call, no comment).
ignore:
  - CKV_AWS_144  # cross-region replication not required
  - CKV_AWS_157  # Multi-AZ handled at infrastructure level
```

A starter template is included at [`.opspilot.yml`](.opspilot.yml) — all entries are commented out so it does nothing until you uncomment them.

## How it works

On every PR, the action fetches the list of changed `.tf` files from the GitHub API, runs Checkov against only those files so you don't get noise from untouched resources, and writes the findings to a JSON file. That JSON goes to `analyze.py`, which calls the LLM once per finding to produce a structured response: severity, explanation, why it matters in production, and exact fix code. `format_comment.py` renders those results into a collapsible markdown comment grouped by severity, which is posted to the PR via the GitHub Issues API. On subsequent pushes to the same PR, OpsPilot updates the existing comment instead of posting a new one.

## Data handling

The resource name, check ID, and the relevant code block from your `.tf` file are sent to the LLM provider for each finding. That means **the provider sees excerpts of your Terraform source.** If your Terraform contains secrets, internal hostnames, or anything you can't share with a third-party API, review the provider's privacy policy before using OpsPilot. Checkov output and LLM responses are not stored anywhere beyond the GitHub Actions run log.

## Limitations

See [docs/limitations.md](docs/limitations.md).

## License

MIT. Solo-maintained — issues and PRs welcome, response time not guaranteed.
