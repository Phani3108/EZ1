"""Tests for the shared OpenTelemetry tracing helper (INFRA-008, Phase 6).

The full integration (real OTLP exporter → real Tempo backend) can only
be verified against actual infrastructure. These tests cover the
control-flow contract:

  * `is_enabled()` reads env honestly.
  * `install(...)` is a no-op when disabled — no opentelemetry imports.
  * `install(...)` is idempotent.
  * `shutdown()` is safe to call even if install never ran.

Real exporter behaviour is covered by the staging chaos-test pass.
"""
import importlib

import pytest

from eduzim_shared import tracing


@pytest.fixture(autouse=True)
def _reset_install_state(monkeypatch):
    """Reset the module-level _INSTALLED flag between tests so
    `test_install_is_idempotent` and friends don't bleed state."""
    monkeypatch.setattr(tracing, "_INSTALLED", False)
    yield
    monkeypatch.setattr(tracing, "_INSTALLED", False)


class TestIsEnabled:

    def test_default_disabled(self, monkeypatch):
        monkeypatch.delenv("EDUZIM_TRACING_ENABLED", raising=False)
        assert tracing.is_enabled() is False

    def test_explicit_false(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TRACING_ENABLED", "false")
        assert tracing.is_enabled() is False

    def test_explicit_true_lowercase(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TRACING_ENABLED", "true")
        assert tracing.is_enabled() is True

    def test_explicit_true_mixed_case(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TRACING_ENABLED", "TRUE")
        assert tracing.is_enabled() is True

    def test_garbage_value_treated_as_false(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TRACING_ENABLED", "maybe")
        assert tracing.is_enabled() is False


class TestInstallDisabled:

    def test_no_op_when_disabled(self, monkeypatch):
        monkeypatch.delenv("EDUZIM_TRACING_ENABLED", raising=False)
        # Must not raise even though opentelemetry isn't installed in
        # the test env.
        tracing.install(service_name="testsvc")
        assert tracing._INSTALLED is False

    def test_no_op_with_app_argument_when_disabled(self, monkeypatch):
        monkeypatch.delenv("EDUZIM_TRACING_ENABLED", raising=False)
        from fastapi import FastAPI
        # Passing app/engine should NOT trigger any import when disabled.
        tracing.install(service_name="testsvc", app=FastAPI())
        assert tracing._INSTALLED is False


class TestInstallEnabledNoLib:

    def test_graceful_when_otel_packages_missing(self, monkeypatch, caplog):
        """If opentelemetry isn't installed but tracing is enabled,
        log a warning and skip — do not crash the process."""
        monkeypatch.setenv("EDUZIM_TRACING_ENABLED", "true")

        # Force the import inside install() to fail. We accomplish this
        # by stubbing `importlib.import_module` for the otel package
        # path — simpler: patch the actual module attribute lookup.
        import sys
        # Pre-poison the imports tracing.install touches first.
        saved = {}
        for mod_prefix in ["opentelemetry.exporter",
                           "opentelemetry.sdk.resources",
                           "opentelemetry.sdk.trace",
                           "opentelemetry.sdk.trace.export"]:
            saved[mod_prefix] = sys.modules.get(mod_prefix)
            sys.modules[mod_prefix] = None  # makes import raise ImportError

        try:
            with caplog.at_level("WARNING"):
                tracing.install(service_name="testsvc")
            assert tracing._INSTALLED is False
            # Should have logged the skip
            assert any("opentelemetry packages not installed" in r.message
                       for r in caplog.records)
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v


class TestShutdownSafety:

    def test_shutdown_before_install_is_noop(self):
        # Must not raise even though install was never called.
        tracing.shutdown()

    def test_shutdown_after_failed_install_is_noop(self):
        # _INSTALLED stays False after a failed/disabled install.
        tracing.shutdown()
        assert tracing._INSTALLED is False


class TestIdempotency:

    def test_install_twice_is_a_noop_second_time(self, monkeypatch):
        """Once installed, a second `install(...)` returns without doing
        anything — important because app_factory may be re-imported in
        test contexts."""
        monkeypatch.setenv("EDUZIM_TRACING_ENABLED", "true")
        # Force-set the installed flag as if a prior install succeeded.
        monkeypatch.setattr(tracing, "_INSTALLED", True)
        # Should be a no-op (and crucially, should not try to import
        # opentelemetry again).
        tracing.install(service_name="testsvc")
        assert tracing._INSTALLED is True
