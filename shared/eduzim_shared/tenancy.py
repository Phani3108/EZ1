"""Tenancy-tier query routing (PH8-2 / DEC-009).

Resolves a `school_id` → the SQLAlchemy engine + session factory that
service should use for that school. Three tiers:

  * `shared`    — default; route to the service's cluster-wide DB
                  (the existing `app.database.engine`).
  * `dedicated` — this school has its own DB. Route to a per-school
                  engine looked up from the registry.
  * `district`  — route to a district-grouped DB looked up by the
                  school's `district_routing_code`.

The shared library is intentionally engine-agnostic: each service
passes in its own `default_engine` (the existing `app.database.engine`),
and the resolver returns that unmodified for `shared` schools. For
`dedicated` / `district`, the resolver consults a registry (env-var or
JSON-file driven) and lazily builds engines per target DB URL.

WHY ENGINE INSTEAD OF SESSION:
  Engines are per-process singletons; sessions are per-request. The
  resolver caches engines (one per target DB) and returns a fresh
  session each call, so we don't accumulate sessions in long-running
  processes. The cache is bounded by the number of distinct DB URLs
  — for a 500-school deployment with mostly `shared`, there's only ~1
  engine; with 50 dedicated schools, ~51.

THREAD-SAFETY:
  The engine cache uses a threading.Lock. Engines themselves are
  thread-safe by SQLAlchemy contract.

REGISTRY SCHEMA:
  Two env vars (or one JSON file) configure the routing:

    EDUZIM_TENANCY_DEDICATED_REGISTRY
      JSON:  {"<school_id_uuid>": "postgresql://.../school_xxx_db", ...}

    EDUZIM_TENANCY_DISTRICT_REGISTRY
      JSON:  {"<district_code>": "postgresql://.../district_xxx_db", ...}

  The resolver reads them at first lookup (cached for the process
  lifetime). For prod, set these via your secrets manager; for tests,
  the resolver accepts an explicit `registry=` arg to skip env.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Generator, Optional

from sqlalchemy.engine import Engine


_logger = logging.getLogger(__name__)


class TenancyConfigError(RuntimeError):
    """Raised when the registry says a school is `dedicated` / `district`
    but no DB URL is configured for it. Fail-loud rather than silently
    falling back to shared."""


@dataclass
class Registry:
    """Two maps + an optional default. Always-loadable from env or
    explicitly passed (in tests)."""
    dedicated: dict[str, str] = field(default_factory=dict)
    district: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Registry":
        dedicated_json = os.environ.get("EDUZIM_TENANCY_DEDICATED_REGISTRY", "")
        district_json = os.environ.get("EDUZIM_TENANCY_DISTRICT_REGISTRY", "")
        try:
            dedicated = json.loads(dedicated_json) if dedicated_json else {}
        except json.JSONDecodeError as e:
            raise TenancyConfigError(
                f"EDUZIM_TENANCY_DEDICATED_REGISTRY is not valid JSON: {e}"
            )
        try:
            district = json.loads(district_json) if district_json else {}
        except json.JSONDecodeError as e:
            raise TenancyConfigError(
                f"EDUZIM_TENANCY_DISTRICT_REGISTRY is not valid JSON: {e}"
            )
        if not isinstance(dedicated, dict) or not isinstance(district, dict):
            raise TenancyConfigError(
                "Tenancy registries must be JSON objects (got non-object)"
            )
        return cls(
            dedicated={k.lower(): v for k, v in dedicated.items()},
            district={k.lower(): v for k, v in district.items()},
        )


# Per-process cache of (db_url → Engine). Created lazily so importing
# the module doesn't require sqlalchemy.
_engine_cache: dict[str, Engine] = {}
_engine_cache_lock = threading.Lock()


def _build_engine(db_url: str, *, echo: bool = False) -> Engine:
    """Build a SQLAlchemy engine.

    Postgres / MySQL / etc.: applies the same pool tuning every service
    uses (PH4-1 standardisation — pool_size=10/20, pool_recycle=1h,
    pool_pre_ping=True). SQLite: drops those args because the pool
    classes SQLite uses (SingletonThreadPool / StaticPool) don't accept
    them.
    """
    from sqlalchemy import create_engine

    kwargs = {"echo": echo}
    if not db_url.startswith("sqlite"):
        kwargs.update({
            "pool_size": 10,
            "max_overflow": 20,
            "pool_recycle": 3600,
            "pool_pre_ping": True,
        })
    return create_engine(db_url, **kwargs)


def _engine_for_url(db_url: str) -> Engine:
    with _engine_cache_lock:
        if db_url not in _engine_cache:
            _engine_cache[db_url] = _build_engine(db_url)
            _logger.info("tenancy.engine_cache.added", extra={"db_url": _redact(db_url)})
        return _engine_cache[db_url]


def _redact(url: str) -> str:
    """Hide credentials in a DB URL for logging."""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return f"{scheme}://{rest}"
    creds, host = rest.rsplit("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://{creds}@{host}"


@dataclass
class TenancyResolution:
    """The result of `resolve(...)`. Tier + engine + maintenance flag."""
    tier: str                         # "shared" | "dedicated" | "district"
    engine: Engine
    maintenance_mode: bool = False    # only set for non-shared tiers


class TenancyResolver:
    """Maps a school's tenancy_tier + identifiers to the right engine.

    Lifecycle:
      * Construct once per service (e.g. on first request, cache as a
        module-level singleton).
      * Pass `default_engine` (your service's existing engine) — used
        for tier=shared schools.
      * Optional `registry`: pass explicit Registry in tests; otherwise
        the resolver reads from env at first call.

    Lookup is O(1) after warmup (registry parsed once, engines cached).
    """

    def __init__(
        self,
        default_engine: Engine,
        *,
        registry: Optional[Registry] = None,
    ):
        self.default_engine = default_engine
        self._registry: Optional[Registry] = registry
        self._registry_lock = threading.Lock()

    def _get_registry(self) -> Registry:
        if self._registry is None:
            with self._registry_lock:
                if self._registry is None:
                    self._registry = Registry.from_env()
        return self._registry

    def resolve(
        self,
        *,
        tier: str,
        school_id: str | None = None,
        district_routing_code: str | None = None,
        maintenance_mode: bool = False,
    ) -> TenancyResolution:
        """Return the engine for the given tier + identifiers.

        Raises TenancyConfigError if `tier in (dedicated, district)` but
        no registry entry exists for the school / district.
        """
        tier = (tier or "shared").lower()

        if tier == "shared":
            return TenancyResolution(
                tier="shared",
                engine=self.default_engine,
                maintenance_mode=False,
            )

        registry = self._get_registry()

        if tier == "dedicated":
            if not school_id:
                raise TenancyConfigError(
                    "tier=dedicated requires a school_id but none was supplied",
                )
            key = school_id.lower()
            db_url = registry.dedicated.get(key)
            if not db_url:
                raise TenancyConfigError(
                    f"school {school_id} marked tenancy_tier=dedicated but no "
                    f"entry in EDUZIM_TENANCY_DEDICATED_REGISTRY",
                )
            return TenancyResolution(
                tier="dedicated",
                engine=_engine_for_url(db_url),
                maintenance_mode=maintenance_mode,
            )

        if tier == "district":
            if not district_routing_code:
                raise TenancyConfigError(
                    "tier=district requires district_routing_code "
                    "but none was supplied",
                )
            key = district_routing_code.lower()
            db_url = registry.district.get(key)
            if not db_url:
                raise TenancyConfigError(
                    f"district {district_routing_code} not found in "
                    f"EDUZIM_TENANCY_DISTRICT_REGISTRY",
                )
            return TenancyResolution(
                tier="district",
                engine=_engine_for_url(db_url),
                maintenance_mode=maintenance_mode,
            )

        raise TenancyConfigError(f"unknown tenancy tier: {tier!r}")

    def session_for(self, **kwargs):
        """Convenience helper: returns a Session from the resolved engine.

        Useful when the caller doesn't need to keep the engine around —
        most route-layer code just wants a session to run a query.
        """
        from sqlalchemy.orm import sessionmaker
        resolution = self.resolve(**kwargs)
        SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=resolution.engine,
        )
        return SessionLocal()


def clear_engine_cache() -> None:
    """Drop all cached engines. Used in tests; in prod, an engine reset
    is rare (only when secrets rotate)."""
    global _engine_cache
    with _engine_cache_lock:
        for engine in _engine_cache.values():
            engine.dispose()
        _engine_cache = {}
