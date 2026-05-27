FROM python:3.11-slim
WORKDIR /app
COPY ./services/reporting-service .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./shared /shared
RUN pip install -e /shared
COPY ./services/reporting-service .

# INFRA-020 (Phase 5): run as a non-root user. groupadd/useradd are
# Debian-flavour (matches the python:3.11-slim base). Container owns
# /app + everything copied into it.
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app && \
    chown -R app:app /app
USER app

# PH2-11 — this container is a pure Kafka consumer. No HTTP server.
# BUG-008 / Phase 4 — migrations moved to services/migrations/.
#
# For local dev where you want the minimal /health endpoint to introspect
# the container, run `uvicorn app.main:app --host 0.0.0.0 --port 8000`
# manually. Production no longer expects this container to listen on a
# port.
CMD ["python", "-m", "app.consumer"]
