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
      - uses: SuryaMadireddy1/Azure_Terraform/action@main
        with:
          groq-api-key: ${{ secrets.GROQ_API_KEY }}
        env:
          GITHUB_TOKEN: ${{ github.token }}
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
```

Add `GROQ_API_KEY` to your repo secrets (Settings → Secrets → Actions). Get a free key at [console.groq.com](https://console.groq.com).

## How it works

On every PR, the action fetches the list of changed `.tf` files from the GitHub API, runs Checkov against only those files so you don't get noise from untouched resources, and writes the findings to a JSON file. That JSON goes to `analyze.py`, which calls the Groq API (Llama 3.3 70B) once per finding to produce a structured response: severity, explanation, why it matters in production, and exact fix code. `format_comment.py` renders those results into a collapsible markdown comment grouped by severity, which is posted to the PR via the GitHub Issues API.

## Data handling

The resource name, check ID, and the relevant code block from your `.tf` file are sent to the Groq API for each finding. That means **Groq sees excerpts of your Terraform source.** If your Terraform contains secrets, internal hostnames, or anything you can't share with a third-party API, review Groq's [privacy policy](https://groq.com/privacy-policy/) before using OpsPilot. Checkov output and LLM responses are not stored anywhere beyond the GitHub Actions run log.

## Limitations

See [docs/limitations.md](docs/limitations.md).

## License

MIT. Solo-maintained — issues and PRs welcome, response time not guaranteed.
