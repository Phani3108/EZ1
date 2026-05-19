FROM python:3.11-slim
WORKDIR /app
COPY ./shared /shared
RUN pip install -e /shared

COPY ./services/communication-service .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./services/communication-service .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
