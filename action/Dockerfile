FROM python:3.11-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl jq \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir checkov==3.2.529 groq openai anthropic click

COPY analyze.py /app/analyze.py
COPY entrypoint.sh /app/entrypoint.sh
COPY format_comment.py /app/format_comment.py
COPY parse_diff.py /app/parse_diff.py
COPY load_policy.py /app/load_policy.py

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
