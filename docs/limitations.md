# Limitations

**OpsPilot explains Checkov findings. It does not replace Checkov or add new detection rules.**
If Checkov doesn't flag it, OpsPilot won't either.

**Blast radius analysis is not supported in v1.**
Cross-resource dependencies (e.g. "this open security group is attached to a subnet that also hosts your RDS instance") require Terraform state access. OpsPilot works from source only.

**Cost estimation is not included in v1.**

**LLM explanations are tested primarily against AWS resources.**
Azure, GCP, and other providers are scanned by Checkov, but the fix suggestions and explanations may be less accurate or specific for non-AWS resources.

**No SLA. Solo-maintained.**
If you need reliability guarantees, fork it.

**Your Terraform source leaves your environment.**
The resource name, check ID, and relevant code block from each flagged `.tf` file are sent to the Groq API. See the [README](../README.md) for details.
