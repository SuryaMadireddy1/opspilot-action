FROM python:3.11-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl jq \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir checkov==3.2.529 groq click

COPY analyze.py /app/
COPY entrypoint.sh /app/
COPY format_comment.py /app/

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
