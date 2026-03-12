"""
EduZim Idempotency Helper
==========================
Tracks processed idempotency keys to prevent duplicate operations.

Two modes:
1. In-memory (for lightweight/dev use)
2. Database-backed (for production — uses an `idempotency_keys` table)

Usage (in-memory):
    from eduzim_shared.idempotency import InMemoryIdempotencyStore
    store = InMemoryIdempotencyStore()
    if store.is_duplicate("key-123"):
        return cached_response
    store.mark_processed("key-123", response_data)

Usage (DB-backed):
    from eduzim_shared.idempotency import DbIdempotencyStore
    store = DbIdempotencyStore(db_session)
    if store.is_duplicate("key-123"):
        return store.get_cached_response("key-123")
    # ... process ...
    store.mark_processed("key-123", response_data)
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session


class InMemoryIdempotencyStore:
    """Simple in-memory idempotency store for dev/testing."""

    def __init__(self, max_size: int = 10000):
        self._store: dict[str, Any] = {}
        self._max_size = max_size

    def is_duplicate(self, key: str) -> bool:
        return key in self._store

    def get_cached_response(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        return entry.get("response") if entry else None

    def mark_processed(self, key: str, response: Any = None) -> None:
        if len(self._store) >= self._max_size:
            # Evict oldest entries (simple strategy)
            oldest = list(self._store.keys())[: self._max_size // 4]
            for k in oldest:
                del self._store[k]
        self._store[key] = {
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "response": response,
        }


def create_idempotency_key_model(Base):
    """
    Factory that creates the IdempotencyKey ORM model bound to a given Base.
    Call this in each service that needs DB-backed idempotency.

    Usage:
        from app.database import Base
        IdempotencyKey = create_idempotency_key_model(Base)
    """

    class IdempotencyKey(Base):
        __tablename__ = "idempotency_keys"

        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        key = Column(String(255), unique=True, nullable=False, index=True)
        response_data = Column(Text, nullable=True)
        created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    return IdempotencyKey


class DbIdempotencyStore:
    """Database-backed idempotency store for production use."""

    def __init__(self, db: Session, model_class):
        self._db = db
        self._model = model_class

    def is_duplicate(self, key: str) -> bool:
        return self._db.query(self._model).filter(self._model.key == key).first() is not None

    def get_cached_response(self, key: str) -> Optional[dict]:
        entry = self._db.query(self._model).filter(self._model.key == key).first()
        if entry and entry.response_data:
            return json.loads(entry.response_data)
        return None

    def mark_processed(self, key: str, response: Any = None) -> None:
        entry = self._model(
            key=key,
            response_data=json.dumps(response, default=str) if response else None,
        )
        self._db.add(entry)
        self._db.commit()


class InboxEventStore:
    """
    Kafka consumer idempotency via inbox_processed_events table.
    Ensures events are processed exactly once.
    """

    def __init__(self, db: Session, model_class):
        self._db = db
        self._model = model_class

    def is_processed(self, event_id: str) -> bool:
        return self._db.query(self._model).filter(self._model.event_id == event_id).first() is not None

    def mark_processed(self, event_id: str, event_type: str) -> None:
        entry = self._model(event_id=event_id, event_type=event_type)
        self._db.add(entry)
        self._db.commit()


def create_inbox_event_model(Base):
    """
    Factory that creates the InboxProcessedEvent model for Kafka consumer idempotency.

    Usage:
        InboxProcessedEvent = create_inbox_event_model(Base)
    """

    class InboxProcessedEvent(Base):
        __tablename__ = "inbox_processed_events"

        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        event_id = Column(String(255), unique=True, nullable=False, index=True)
        event_type = Column(String(255), nullable=False)
        processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    return InboxProcessedEvent
