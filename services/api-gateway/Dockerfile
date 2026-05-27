FROM python:3.11-slim
WORKDIR /app
COPY ./services/api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the shared `eduzim_shared` package (every other service
# does this). The gateway uses it for the audit substrate +
# redis_client + app_factory imports; without this the container
# crashes on boot.
COPY ./shared /shared
RUN pip install -e /shared

COPY ./services/api-gateway .

# INFRA-020 (Phase 5): run as a non-root user. groupadd/useradd are
# Debian-flavour (matches the python:3.11-slim base). Container owns
# /app + everything copied into it.
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app && \
    chown -R app:app /app
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
