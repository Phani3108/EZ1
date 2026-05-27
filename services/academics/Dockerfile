FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ./services/academics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./shared /shared
RUN pip install -e /shared

# Copy application code
COPY ./services/academics .

# INFRA-020 (Phase 5): non-root user.
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app && \
    chown -R app:app /app
USER app

# BUG-008 / Phase 4: migrations moved to the dedicated `migrations`
# container (services/migrations/Dockerfile). Service containers
# depend_on it via `service_completed_successfully` and just boot the
# web server here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

EXPOSE 8000
