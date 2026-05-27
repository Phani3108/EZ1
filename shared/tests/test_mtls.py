"""Tests for the shared mTLS helper (INFRA-019 / Phase 5)."""
import os
import ssl

import pytest

from eduzim_shared import mtls


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("EDUZIM_TLS_ENABLED", "EDUZIM_TLS_CA_CERT",
              "EDUZIM_TLS_SERVER_CERT", "EDUZIM_TLS_SERVER_KEY"):
        monkeypatch.delenv(k, raising=False)


def _make_dummy_certs(tmp_path):
    ca = tmp_path / "ca.crt"; ca.write_text("dummy-ca")
    crt = tmp_path / "server.crt"; crt.write_text("dummy-crt")
    key = tmp_path / "server.key"; key.write_text("dummy-key")
    return str(ca), str(crt), str(key)


class TestDisabled:

    def test_uvicorn_kwargs_empty_when_disabled(self):
        assert mtls.uvicorn_kwargs() == {}

    def test_httpx_kwargs_empty_when_disabled(self):
        assert mtls.httpx_kwargs() == {}

    def test_http_scheme_is_http(self):
        assert mtls.http_scheme() == "http"

    def test_explicit_false_also_disabled(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TLS_ENABLED", "false")
        assert mtls.uvicorn_kwargs() == {}


class TestEnabledHappyPath:

    def test_uvicorn_kwargs_populated(self, tmp_path, monkeypatch):
        ca, crt, key = _make_dummy_certs(tmp_path)
        monkeypatch.setenv("EDUZIM_TLS_ENABLED", "true")
        monkeypatch.setenv("EDUZIM_TLS_CA_CERT", ca)
        monkeypatch.setenv("EDUZIM_TLS_SERVER_CERT", crt)
        monkeypatch.setenv("EDUZIM_TLS_SERVER_KEY", key)

        kw = mtls.uvicorn_kwargs()
        assert kw["ssl_certfile"] == crt
        assert kw["ssl_keyfile"] == key
        assert kw["ssl_ca_certs"] == ca
        assert kw["ssl_cert_reqs"] == ssl.CERT_REQUIRED

    def test_httpx_kwargs_populated(self, tmp_path, monkeypatch):
        ca, crt, key = _make_dummy_certs(tmp_path)
        monkeypatch.setenv("EDUZIM_TLS_ENABLED", "true")
        monkeypatch.setenv("EDUZIM_TLS_CA_CERT", ca)
        monkeypatch.setenv("EDUZIM_TLS_SERVER_CERT", crt)
        monkeypatch.setenv("EDUZIM_TLS_SERVER_KEY", key)

        kw = mtls.httpx_kwargs()
        assert kw["verify"] == ca
        assert kw["cert"] == (crt, key)

    def test_http_scheme_is_https(self, tmp_path, monkeypatch):
        ca, crt, key = _make_dummy_certs(tmp_path)
        monkeypatch.setenv("EDUZIM_TLS_ENABLED", "true")
        monkeypatch.setenv("EDUZIM_TLS_CA_CERT", ca)
        monkeypatch.setenv("EDUZIM_TLS_SERVER_CERT", crt)
        monkeypatch.setenv("EDUZIM_TLS_SERVER_KEY", key)
        assert mtls.http_scheme() == "https"


class TestEnabledMisconfigured:

    def test_enabled_without_ca_path_raises(self, monkeypatch):
        monkeypatch.setenv("EDUZIM_TLS_ENABLED", "true")
        with pytest.raises(RuntimeError, match="cert paths missing"):
            mtls.uvicorn_kwargs()

    def test_enabled_with_missing_file_raises(self, tmp_path, monkeypatch):
        # Cert env vars set but the files don't actually exist.
        monkeypatch.setenv("EDUZIM_TLS_ENABLED", "true")
        monkeypatch.setenv("EDUZIM_TLS_CA_CERT", str(tmp_path / "missing.crt"))
        monkeypatch.setenv("EDUZIM_TLS_SERVER_CERT", str(tmp_path / "missing.crt"))
        monkeypatch.setenv("EDUZIM_TLS_SERVER_KEY", str(tmp_path / "missing.key"))
        with pytest.raises(RuntimeError, match="does not exist"):
            mtls.uvicorn_kwargs()
