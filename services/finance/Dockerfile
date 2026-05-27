FROM python:3.11-slim
WORKDIR /app
COPY ./services/finance/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./shared /shared
RUN pip install -e /shared
COPY ./services/finance .

# INFRA-020 (Phase 5): run as a non-root user. groupadd/useradd are
# Debian-flavour (matches the python:3.11-slim base). Container owns
# /app + everything copied into it.
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app && \
    chown -R app:app /app
USER app

# BUG-008 / Phase 4: migrations live in services/migrations/.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
