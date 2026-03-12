FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ./services/auth-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./shared /shared
RUN pip install -e /shared

# Copy application code
COPY ./services/auth-service .

# Run migrations and start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

EXPOSE 8000
