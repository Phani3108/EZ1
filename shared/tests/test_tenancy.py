"""Tests for the shared tenancy resolver (PH8-2 / DEC-009)."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from eduzim_shared.tenancy import (
    Registry,
    TenancyConfigError,
    TenancyResolution,
    TenancyResolver,
    clear_engine_cache,
)


# ─── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def default_engine():
    """A throwaway in-memory engine standing in for the service's default."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _clean_engine_cache():
    """Reset module-level cache between tests so they don't share engines."""
    clear_engine_cache()
    yield
    clear_engine_cache()


# ─── Registry ─────────────────────────────────────────────────────


class TestRegistry:

    def test_from_env_empty(self, monkeypatch):
        monkeypatch.delenv("EDUZIM_TENANCY_DEDICATED_REGISTRY", raising=False)
        monkeypatch.delenv("EDUZIM_TENANCY_DISTRICT_REGISTRY", raising=False)
        r = Registry.from_env()
        assert r.dedicated == {}
        assert r.district == {}

    def test_from_env_loads_dedicated(self, monkeypatch):
        sid = "11111111-1111-1111-1111-111111111111"
        monkeypatch.setenv(
            "EDUZIM_TENANCY_DEDICATED_REGISTRY",
            json.dumps({sid: "postgresql://eduzim:x@host/school_x_db"}),
        )
        r = Registry.from_env()
        # Keys are lowercased on load.
        assert r.dedicated[sid.lower()] == "postgresql://eduzim:x@host/school_x_db"

    def test_from_env_loads_district(self, monkeypatch):
        monkeypatch.setenv(
            "EDUZIM_TENANCY_DISTRICT_REGISTRY",
            json.dumps({"hre-cn": "postgresql://eduzim:x@host/hre_db"}),
        )
        r = Registry.from_env()
        assert r.district["hre-cn"] == "postgresql://eduzim:x@host/hre_db"

    def test_invalid_json_raises(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TENANCY_DEDICATED_REGISTRY", "{not json")
        with pytest.raises(TenancyConfigError, match="not valid JSON"):
            Registry.from_env()

    def test_non_object_json_raises(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TENANCY_DEDICATED_REGISTRY", json.dumps([]))
        with pytest.raises(TenancyConfigError, match="must be JSON objects"):
            Registry.from_env()


# ─── TenancyResolver.resolve() ────────────────────────────────────


class TestResolveShared:
    """Tier=shared is the hot path: returns the default engine, no
    registry lookup, no engine cache pressure."""

    def test_returns_default_engine(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        out = resolver.resolve(tier="shared")
        assert isinstance(out, TenancyResolution)
        assert out.tier == "shared"
        assert out.engine is default_engine
        assert out.maintenance_mode is False

    def test_empty_string_defaults_to_shared(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        out = resolver.resolve(tier="")
        assert out.tier == "shared"
        assert out.engine is default_engine

    def test_none_defaults_to_shared(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        out = resolver.resolve(tier=None)
        assert out.tier == "shared"
        assert out.engine is default_engine

    def test_shared_ignores_school_id_and_district(self, default_engine):
        """A shared school doesn't need a registry entry even if other
        identifiers are passed."""
        resolver = TenancyResolver(default_engine, registry=Registry())
        out = resolver.resolve(
            tier="shared",
            school_id="11111111-1111-1111-1111-111111111111",
            district_routing_code="hre-cn",
        )
        assert out.engine is default_engine


class TestResolveDedicated:

    def test_resolves_via_registry(self, default_engine):
        sid = "22222222-2222-2222-2222-222222222222"
        registry = Registry(dedicated={sid: "sqlite://"})
        resolver = TenancyResolver(default_engine, registry=registry)
        out = resolver.resolve(tier="dedicated", school_id=sid)
        assert out.tier == "dedicated"
        # The engine is NOT the default — it's the per-school one.
        assert out.engine is not default_engine

    def test_missing_school_id_raises(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        with pytest.raises(TenancyConfigError, match="requires a school_id"):
            resolver.resolve(tier="dedicated")

    def test_missing_registry_entry_raises(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        with pytest.raises(TenancyConfigError, match="no entry in"):
            resolver.resolve(
                tier="dedicated",
                school_id="33333333-3333-3333-3333-333333333333",
            )

    def test_case_insensitive_school_id_lookup(self, default_engine):
        """School-id matching is case-insensitive: registry stores
        lowercased, lookup matches regardless of caller casing."""
        sid_upper = "44444444-4444-4444-4444-444444444444".upper()
        registry = Registry(dedicated={sid_upper.lower(): "sqlite://"})
        resolver = TenancyResolver(default_engine, registry=registry)
        out = resolver.resolve(tier="dedicated", school_id=sid_upper)
        assert out.tier == "dedicated"

    def test_maintenance_mode_propagates(self, default_engine):
        sid = "55555555-5555-5555-5555-555555555555"
        registry = Registry(dedicated={sid: "sqlite://"})
        resolver = TenancyResolver(default_engine, registry=registry)
        out = resolver.resolve(
            tier="dedicated", school_id=sid, maintenance_mode=True,
        )
        assert out.maintenance_mode is True


class TestResolveDistrict:

    def test_resolves_via_district_code(self, default_engine):
        registry = Registry(district={"hre-cn": "sqlite://"})
        resolver = TenancyResolver(default_engine, registry=registry)
        out = resolver.resolve(
            tier="district",
            district_routing_code="hre-cn",
        )
        assert out.tier == "district"
        assert out.engine is not default_engine

    def test_case_insensitive_district_code(self, default_engine):
        registry = Registry(district={"hre-cn": "sqlite://"})
        resolver = TenancyResolver(default_engine, registry=registry)
        out = resolver.resolve(
            tier="district",
            district_routing_code="HRE-CN",
        )
        assert out.tier == "district"

    def test_missing_district_code_raises(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        with pytest.raises(TenancyConfigError, match="requires district_routing_code"):
            resolver.resolve(tier="district")

    def test_unknown_district_raises(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        with pytest.raises(TenancyConfigError, match="not found in"):
            resolver.resolve(
                tier="district",
                district_routing_code="unknown-district",
            )


class TestUnknownTier:

    def test_unknown_tier_raises(self, default_engine):
        resolver = TenancyResolver(default_engine, registry=Registry())
        with pytest.raises(TenancyConfigError, match="unknown tenancy tier"):
            resolver.resolve(tier="multi-region")


# ─── Engine caching ───────────────────────────────────────────────


class TestEngineCache:

    def test_two_lookups_same_school_share_engine(self, default_engine):
        sid = "66666666-6666-6666-6666-666666666666"
        registry = Registry(dedicated={sid: "sqlite://"})
        resolver = TenancyResolver(default_engine, registry=registry)
        out1 = resolver.resolve(tier="dedicated", school_id=sid)
        out2 = resolver.resolve(tier="dedicated", school_id=sid)
        # Same engine instance reused (cache hit).
        assert out1.engine is out2.engine

    def test_two_schools_different_dbs_get_different_engines(self, default_engine):
        sa = "77777777-7777-7777-7777-777777777777"
        sb = "88888888-8888-8888-8888-888888888888"
        registry = Registry(dedicated={
            sa: "sqlite:///./_a.db",
            sb: "sqlite:///./_b.db",
        })
        resolver = TenancyResolver(default_engine, registry=registry)
        out_a = resolver.resolve(tier="dedicated", school_id=sa)
        out_b = resolver.resolve(tier="dedicated", school_id=sb)
        assert out_a.engine is not out_b.engine

    def test_clear_cache(self, default_engine):
        sid = "99999999-9999-9999-9999-999999999999"
        registry = Registry(dedicated={sid: "sqlite://"})
        resolver = TenancyResolver(default_engine, registry=registry)
        out1 = resolver.resolve(tier="dedicated", school_id=sid)
        clear_engine_cache()
        out2 = resolver.resolve(tier="dedicated", school_id=sid)
        # After cache clear, a fresh engine instance was built.
        assert out1.engine is not out2.engine


# ─── session_for convenience ───────────────────────────────────────


class TestSessionFor:

    def test_session_for_returns_usable_session(self, default_engine):
        from sqlalchemy import text
        resolver = TenancyResolver(default_engine, registry=Registry())
        session = resolver.session_for(tier="shared")
        try:
            # SQLite trivial query — confirms the session is wired.
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1
        finally:
            session.close()


# ─── Env-driven lazy registry load ─────────────────────────────────


class TestLazyEnvLoad:

    def test_registry_loaded_from_env_on_first_resolve(self, default_engine, monkeypatch):
        sid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        monkeypatch.setenv(
            "EDUZIM_TENANCY_DEDICATED_REGISTRY",
            json.dumps({sid: "sqlite://"}),
        )
        # Construct WITHOUT explicit registry; should read env on first
        # call.
        resolver = TenancyResolver(default_engine)
        out = resolver.resolve(tier="dedicated", school_id=sid)
        assert out.tier == "dedicated"

    def test_registry_cached_after_first_load(self, default_engine, monkeypatch):
        sid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        monkeypatch.setenv(
            "EDUZIM_TENANCY_DEDICATED_REGISTRY",
            json.dumps({sid: "sqlite://"}),
        )
        resolver = TenancyResolver(default_engine)
        resolver.resolve(tier="dedicated", school_id=sid)
        # Mutate env after first load — should NOT affect resolver
        # (it cached the registry on first call).
        monkeypatch.setenv("EDUZIM_TENANCY_DEDICATED_REGISTRY", "{}")
        out = resolver.resolve(tier="dedicated", school_id=sid)
        assert out.tier == "dedicated"  # still resolves
