"""
Service-to-Service client for validating class/year existence in school-service.

In production: makes HTTP calls to school-service.
In tests: injectable mock via dependency injection.
"""
import logging
import uuid
from typing import Optional, Protocol

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class SchoolServiceClient(Protocol):
    """Protocol for school-service client (enables mocking in tests)."""

    def validate_class(self, class_id: uuid.UUID, school_id: uuid.UUID,
                       token: str) -> Optional[dict]: ...

    def validate_academic_year(self, year_id: uuid.UUID, school_id: uuid.UUID,
                                token: str) -> Optional[dict]: ...


class HttpSchoolServiceClient:
    """Production HTTP client that calls school-service endpoints."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or get_settings().SCHOOL_SERVICE_URL

    def validate_class(self, class_id: uuid.UUID, school_id: uuid.UUID,
                       token: str) -> Optional[dict]:
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v1/classes",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if resp.status_code != 200:
                return None
            body = resp.json()
            classes = body.get("data", [])
            for cls in classes:
                if cls["id"] == str(class_id) and cls["school_id"] == str(school_id):
                    return cls
            return None
        except Exception as e:
            logger.error(f"School service call failed: {e}")
            return None

    def validate_academic_year(self, year_id: uuid.UUID, school_id: uuid.UUID,
                                token: str) -> Optional[dict]:
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v1/academics/years",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
            if resp.status_code != 200:
                return None
            body = resp.json()
            years = body.get("data", [])
            for y in years:
                if y["id"] == str(year_id) and y["school_id"] == str(school_id):
                    return y
            return None
        except Exception as e:
            logger.error(f"School service call failed: {e}")
            return None


class MockSchoolServiceClient:
    """Mock client for unit tests — pre-loaded with known classes/years."""

    def __init__(self):
        self._classes: dict[str, dict] = {}
        self._years: dict[str, dict] = {}

    def add_class(self, class_id: uuid.UUID, school_id: uuid.UUID, name: str = "Grade 1"):
        self._classes[str(class_id)] = {
            "id": str(class_id), "school_id": str(school_id), "name": name,
        }

    def add_year(self, year_id: uuid.UUID, school_id: uuid.UUID, name: str = "2026"):
        self._years[str(year_id)] = {
            "id": str(year_id), "school_id": str(school_id), "name": name,
        }

    def validate_class(self, class_id: uuid.UUID, school_id: uuid.UUID,
                       token: str = "") -> Optional[dict]:
        cls = self._classes.get(str(class_id))
        if cls and cls["school_id"] == str(school_id):
            return cls
        return None

    def validate_academic_year(self, year_id: uuid.UUID, school_id: uuid.UUID,
                                token: str = "") -> Optional[dict]:
        year = self._years.get(str(year_id))
        if year and year["school_id"] == str(school_id):
            return year
        return None
