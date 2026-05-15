#!/usr/bin/env bash
set -euo pipefail

export GROQ_API_KEY="${GROQ_API_KEY:-}"
if [[ -z "${GROQ_API_KEY}" ]]; then
  echo "Error: GROQ_API_KEY is required."
  exit 1
fi
WS="${GITHUB_WORKSPACE:-/github/workspace}"
cd "$WS"

API_URL="${GITHUB_API_URL:-https://api.github.com}"
TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN is required}"

OWNER="${GITHUB_REPOSITORY%%/*}"
REPO="${GITHUB_REPOSITORY#*/}"

PR_NUMBER=""
if [[ -n "${GITHUB_EVENT_PATH:-}" && -f "${GITHUB_EVENT_PATH}" ]]; then
  PR_NUMBER="$(jq -r '.pull_request.number // empty' "${GITHUB_EVENT_PATH}" 2>/dev/null || true)"
fi
if [[ -z "${PR_NUMBER:-}" && "${GITHUB_REF_NAME:-}" =~ ^([0-9]+)/merge$ ]]; then
  PR_NUMBER="${BASH_REMATCH[1]}"
fi

post_comment() {
  local body_file="$1"
  if [[ -z "${PR_NUMBER:-}" ]]; then
    echo "No pull request number detected; skipping PR comment." >&2
    return 0
  fi
  jq -n --rawfile body "$body_file" '{body: $body}' \
    | curl -sS -f \
      -X POST \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "${API_URL}/repos/${OWNER}/${REPO}/issues/${PR_NUMBER}/comments" \
      -d @- >/dev/null
}

list_pr_tf_files() {
  local page=1
  while true; do
    local url resp count
    url="${API_URL}/repos/${OWNER}/${REPO}/pulls/${PR_NUMBER}/files?per_page=100&page=${page}"
    resp="$(curl -sS -f -H "Authorization: Bearer ${TOKEN}" -H "Accept: application/vnd.github+json" "${url}")"
    count="$(echo "${resp}" | jq 'length')"
    if [[ "${count}" == "0" ]]; then
      break
    fi
    echo "${resp}" | jq -r '.[] | select(.filename|test("\\.tf$")) | select(.status != "removed") | .filename'
    page=$((page + 1))
  done
}

CHECKOV_EXTRA=()
if [[ -n "${INPUT_CHECKOV_SEVERITY:-}" ]]; then
  IFS='|' read -ra SEV_PARTS <<< "${INPUT_CHECKOV_SEVERITY}"
  for part in "${SEV_PARTS[@]}"; do
    trimmed="${part#"${part%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    [[ -z "${trimmed}" ]] && continue
    upper="$(printf '%s' "${trimmed}" | tr '[:lower:]' '[:upper:]')"
    CHECKOV_EXTRA+=(--check-severity "${upper}")
  done
fi

tf_files=()
if [[ -n "${PR_NUMBER:-}" ]]; then
  while IFS= read -r line; do
    [[ -n "${line}" ]] && tf_files+=("${line}")
  done < <(list_pr_tf_files)
else
  echo "No PR context; scanning all *.tf under workspace (best-effort)." >&2
  while IFS= read -r -d '' f; do
    tf_files+=("${f#${WS}/}")
  done < <(find "${WS}" -type f -name '*.tf' -print0 2>/dev/null || true)
fi

if [[ "${#tf_files[@]}" -eq 0 ]]; then
  echo '{"check_type":"terraform","results":{"failed_checks":[]}}' >"${WS}/findings.json"
  python3 /app/analyze.py --checkov-output "${WS}/findings.json"
  python3 /app/format_comment.py "${WS}/opspilot-results.json" >/tmp/opspilot-comment.md
  post_comment /tmp/opspilot-comment.md || true
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "findings-json=${WS}/opspilot-results.json" >>"${GITHUB_OUTPUT}"
  fi
  exit 0
fi

checkov_cmd=(checkov -o json --framework terraform)
if [[ "${#CHECKOV_EXTRA[@]}" -gt 0 ]]; then
  checkov_cmd+=("${CHECKOV_EXTRA[@]}")
fi
added=0
for rel in "${tf_files[@]}"; do
  abs="${WS}/${rel}"
  if [[ -f "${abs}" ]]; then
    checkov_cmd+=(--file "${abs}")
    added=$((added + 1))
  else
    echo "warning: PR lists ${rel} but file is missing locally; skipping." >&2
  fi
done

if [[ "${added}" -eq 0 ]]; then
  echo "No local .tf files available for Checkov." >&2
  echo '{"check_type":"terraform","results":{"failed_checks":[]}}' >"${WS}/findings.json"
else
  "${checkov_cmd[@]}" >"${WS}/findings.json"
fi

python3 /app/analyze.py --checkov-output "${WS}/findings.json"

python3 /app/format_comment.py "${WS}/opspilot-results.json" >/tmp/opspilot-comment.md
post_comment /tmp/opspilot-comment.md || {
  echo "warning: failed to post PR comment (permissions or API error)." >&2
}

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "findings-json=${WS}/opspilot-results.json" >>"${GITHUB_OUTPUT}"
fi
