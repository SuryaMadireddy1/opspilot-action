FROM python:3.11-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl jq \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir checkov groq click

COPY opspilot/analyze.py /app/analyze.py
COPY action/entrypoint.sh /app/entrypoint.sh
COPY action/format_comment.py /app/format_comment.py

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
