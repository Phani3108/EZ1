"""Unit tests for eduzim_shared modules."""
import json
import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---- Logging Tests ----

def test_setup_logging_plain():
    from eduzim_shared.logging import setup_logging, get_logger, _configured
    import eduzim_shared.logging as log_mod

    # Reset configured state for test
    log_mod._configured = False
    setup_logging(service_name="test-service", json_output=False)
    logger = get_logger("test")
    assert logger is not None
    log_mod._configured = False  # Reset for other tests


def test_json_formatter():
    from eduzim_shared.logging import JSONFormatter
    formatter = JSONFormatter(service_name="unit-test")
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py",
        lineno=1, msg="hello world", args=(), exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["service"] == "unit-test"
    assert parsed["message"] == "hello world"
    assert "timestamp" in parsed


# ---- Error Tests ----

def test_not_found_error():
    from eduzim_shared.errors import NotFoundError
    err = NotFoundError("Student", "abc-123")
    assert err.status_code == 404
    assert err.error == "not_found"
    assert "abc-123" in err.detail


def test_conflict_error():
    from eduzim_shared.errors import ConflictError
    err = ConflictError("Email already registered")
    assert err.status_code == 409


def test_tenant_isolation_error():
    from eduzim_shared.errors import TenantIsolationError
    err = TenantIsolationError()
    assert err.status_code == 403
    assert "another school" in err.detail


def test_error_handler_registration():
    from eduzim_shared.errors import register_exception_handlers, NotFoundError
    app = FastAPI()
    register_exception_handlers(app, service_name="test")

    @app.get("/fail")
    def fail():
        raise NotFoundError("Item", "xyz")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/fail")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "not_found"
    assert body["service"] == "test"


# ---- Response Envelope Tests ----

def test_success_response():
    from eduzim_shared.response import success_response
    resp = success_response(data={"id": "123", "name": "Test"})
    body = json.loads(resp.body)
    assert "data" in body
    assert body["data"]["id"] == "123"
    assert "meta" in body
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]


def test_paginated_response():
    from eduzim_shared.response import paginated_response
    resp = paginated_response(
        data=[{"id": 1}, {"id": 2}],
        page=1, page_size=50, total=200,
    )
    body = json.loads(resp.body)
    assert body["meta"]["page"] == 1
    assert body["meta"]["total"] == 200
    assert body["meta"]["has_next"] is True


def test_paginated_response_last_page():
    from eduzim_shared.response import paginated_response
    resp = paginated_response(
        data=[{"id": 1}],
        page=4, page_size=50, total=200,
    )
    body = json.loads(resp.body)
    assert body["meta"]["has_next"] is False


def test_error_response():
    from eduzim_shared.response import error_response
    resp = error_response(
        code="VALIDATION_ERROR", message="Invalid email", status_code=422,
    )
    body = json.loads(resp.body)
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert resp.status_code == 422


# ---- Middleware Tests ----

def test_request_id_middleware_generates():
    from eduzim_shared.middleware import RequestIdMiddleware
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    resp = client.get("/test")
    assert "X-Request-Id" in resp.headers
    # Should be valid UUID
    uuid.UUID(resp.headers["X-Request-Id"])


def test_request_id_middleware_passes_through():
    from eduzim_shared.middleware import RequestIdMiddleware
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"ok": True}

    client = TestClient(app)
    custom_id = str(uuid.uuid4())
    resp = client.get("/test", headers={"X-Request-Id": custom_id})
    assert resp.headers["X-Request-Id"] == custom_id


# ---- Idempotency Tests ----

def test_in_memory_idempotency():
    from eduzim_shared.idempotency import InMemoryIdempotencyStore
    store = InMemoryIdempotencyStore()
    assert not store.is_duplicate("key-1")
    store.mark_processed("key-1", {"result": "ok"})
    assert store.is_duplicate("key-1")
    assert store.get_cached_response("key-1") == {"result": "ok"}


def test_in_memory_idempotency_eviction():
    from eduzim_shared.idempotency import InMemoryIdempotencyStore
    store = InMemoryIdempotencyStore(max_size=10)
    for i in range(15):
        store.mark_processed(f"key-{i}")
    # After eviction, store should have fewer than 15 entries
    assert not store.is_duplicate("key-0")  # Evicted


# ---- Kafka Config Tests ----

def test_kafka_topics():
    from eduzim_shared.kafka.config import Topics
    topics = Topics.all_topics()
    assert len(topics) == 13  # Phase 1: 13 topics
    assert "eduzim.auth.user.created.v1" in topics
    assert "eduzim.attendance.recorded.v1" in topics
    for t in topics:
        assert t.startswith("eduzim.")
        assert t.endswith(".v1")


def test_kafka_producer_config():
    from eduzim_shared.kafka.config import KafkaConfig
    config = KafkaConfig(bootstrap_servers="kafka:9092")
    pc = config.producer_config()
    assert pc["bootstrap.servers"] == "kafka:9092"
    assert pc["enable.idempotence"] is True
    assert pc["acks"] == "all"


def test_kafka_consumer_config():
    from eduzim_shared.kafka.config import KafkaConfig
    config = KafkaConfig(bootstrap_servers="kafka:9092", group_id="test-group")
    cc = config.consumer_config()
    assert cc["group.id"] == "test-group"
    assert cc["enable.auto.commit"] is False


# ---- App Factory Tests ----

def test_app_factory():
    from eduzim_shared.app_factory import create_app
    app = create_app(title="Test Service", service_name="test-svc", debug=True)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "test-svc"
    assert body["status"] == "healthy"


def test_app_factory_root():
    from eduzim_shared.app_factory import create_app
    app = create_app(title="Test", service_name="test-svc", debug=True)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "test-svc"
