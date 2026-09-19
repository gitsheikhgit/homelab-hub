FROM python:3.12-slim

# ── System tools ──────────────────────────────────────────────────────────────
# smartmontools  → SMART health, temperature (requires privileged: true in compose)
# hdparm         → Fallback HDD info for drives without full SMART support
# nvme-cli       → NVMe SSD telemetry (nvme smart-log)
# docker.io      → Docker CLI for fleet management (communicates via /var/run/docker.sock)
# curl           → Health checks, external API calls
# procps         → ps / free / etc. (used by psutil)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    smartmontools \
    hdparm \
    nvme-cli \
    procps \
    docker-cli \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure data directory and upload paths exist
RUN mkdir -p /app/data/uploads/icons /app/data/uploads/wallpapers

ENV PYTHONUNBUFFERED=1
ENV PORT=8095

# Tell the app it's running inside Docker (skips sudo, calls smartctl directly as root)
ENV RUNNING_IN_DOCKER=1

# Host /proc and /sys are bind-mounted from the host at these paths (see docker-compose.yml)
ENV HOST_PROC=/host/proc
ENV HOST_SYS=/host/sys

EXPOSE 8095

# Persistent volume: cards, settings, custom uploads
VOLUME ["/app/data"]

CMD ["python3", "app.py"]
