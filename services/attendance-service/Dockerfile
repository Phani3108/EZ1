FROM python:3.11-slim
WORKDIR /app
COPY ./services/attendance-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./shared /shared
RUN pip install -e /shared
COPY ./services/attendance-service .
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]
