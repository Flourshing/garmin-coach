FROM python:3.12-slim-bookworm AS python-runtime
FROM node:24.22.1-bookworm-slim

COPY --from=python-runtime /usr/local /usr/local
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git libatomic1 libexpat1 libffi8 libsqlite3-0 libbz2-1.0 liblzma5 libssl3 zlib1g tzdata fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
COPY deploy/runtime-package.json /opt/openclaw/package.json
RUN npm install --global npm@11.16.0 --ignore-scripts --no-audit --no-fund
RUN cd /opt/openclaw && npm install --omit=dev --no-audit --no-fund
COPY requirements.txt /opt/garmin/requirements.txt
RUN python3 -m venv /opt/garmin/venv && /opt/garmin/venv/bin/pip install --no-cache-dir -r /opt/garmin/requirements.txt

WORKDIR /app
COPY collect.py garmin_service.py garmin_mcp_server.py garmin_data.py garmin_extended.py garmin_charts.py prepare_openclaw.py prepare_daily_job.py configure_models.py /app/
COPY coach /app/coach
COPY deploy/cloud_start.py /app/cloud_start.py
COPY deploy/codex-restricted-settings.json /app/deploy/codex-restricted-settings.json
COPY deploy/deepseek-provider.json /app/deploy/deepseek-provider.json
COPY deploy/daily-report-prompt.txt /app/deploy/daily-report-prompt.txt
ENV PATH="/opt/garmin/venv/bin:/opt/openclaw/node_modules/.bin:${PATH}" \
    OPENCLAW_STATE_DIR=/data/openclaw \
    OPENCLAW_CONFIG_PATH=/data/openclaw/openclaw.json \
    OPENCLAW_WORKSPACE_DIR=/data/coach-workspace \
    GARMIN_DATA_DIR=/data/garmin \
    GARMIN_CLOUD=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=Asia/Shanghai \
    PORT=8080
EXPOSE 8080
VOLUME ["/data"]
CMD ["python", "cloud_start.py"]
