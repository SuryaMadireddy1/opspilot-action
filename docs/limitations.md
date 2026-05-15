# Limitations

**OpsPilot explains Checkov findings. It does not replace Checkov or add new detection rules.**
If Checkov doesn't flag it, OpsPilot won't either.

**Pull requests only.**
The action posts a comment on pull requests. Push-to-main, scheduled runs, and other events skip the comment step unless a PR number is present in the event payload.

**`actions/checkout` must run before OpsPilot.**
The action resolves changed `.tf` file paths against `GITHUB_WORKSPACE`. If the repo isn't checked out, there are no files to scan.

**Only changed, non-deleted `.tf` files are scanned.**
Files not part of the PR diff, and files with status `removed`, are skipped.

**Permissions required: `pull-requests: write`.**
The workflow needs a `GITHUB_TOKEN` that can read pull requests and create issue comments.

**Blast radius analysis is not supported in v1.**
Cross-resource dependencies (e.g. "this open security group is attached to a subnet that also hosts your RDS instance") require Terraform state access. OpsPilot works from source only.

**Cost estimation is not included in v1.**

**LLM explanations are tested primarily against AWS resources.**
Azure, GCP, and other providers are scanned by Checkov, but fix suggestions may be less accurate for non-AWS resources.

**Model JSON parse failures are silently skipped.**
If the Groq model returns malformed JSON for a finding, `analyze.py` logs a warning and skips that finding. The PR comment will have fewer findings than Checkov reported.

**Severity mapping.**
Model-returned severities map to comment sections as follows: `critical` → Critical, `high` / `warning` → High, `info` → Info. Anything else goes under Other.

**`checkov-severity` input behavior.**
The value is split on `|`, uppercased, and passed to Checkov as repeated `--check-severity` flags (e.g. `critical|high` → `--check-severity CRITICAL --check-severity HIGH`).

**No SLA. Solo-maintained.**
If you need reliability guarantees, fork it.

**Your Terraform source leaves your environment.**
The resource name, check ID, and relevant code block from each flagged `.tf` file are sent to the Groq API. See the [README](../README.md) for details.
