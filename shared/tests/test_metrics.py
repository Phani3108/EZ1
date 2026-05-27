"""Tests for the shared Prometheus metrics middleware (INFRA-007, Phase 6)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from eduzim_shared import metrics


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/widgets")
    def list_widgets():
        return {"data": []}

    @app.get("/widgets/{wid}")
    def get_widget(wid: int):
        if wid == 999:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="not found")
        return {"id": wid}

    @app.post("/widgets")
    def create_widget():
        return {"created": True}

    return app


class TestMetricsInstallation:

    def test_metrics_endpoint_is_added(self):
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        r = client.get("/metrics")
        assert r.status_code == 200
        # Prometheus exposition format starts with HELP/TYPE comments.
        assert "# HELP eduzim_http_requests_total" in r.text
        assert "# TYPE eduzim_http_requests_total counter" in r.text

    def test_metrics_endpoint_not_self_recorded(self):
        """Hitting /metrics should NOT increment the counter — otherwise
        every Prometheus scrape would inflate its own stats."""
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        client.get("/metrics")
        client.get("/metrics")
        body = client.get("/metrics").text
        # The /metrics route should appear in NO counter line.
        for line in body.splitlines():
            if line.startswith("eduzim_http_requests_total"):
                assert 'route="/metrics"' not in line


class TestRequestCounter:

    def test_successful_request_counted(self):
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        client.get("/widgets")
        body = client.get("/metrics").text
        assert 'eduzim_http_requests_total{method="GET",route="/widgets",service="testsvc",status="200"} 1.0' in body

    def test_path_template_used_not_raw_path(self):
        """`/widgets/{wid}` should be the route label — NOT `/widgets/42` —
        so high-cardinality IDs don't blow up time-series count."""
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        client.get("/widgets/42")
        client.get("/widgets/99")
        client.get("/widgets/7")
        body = client.get("/metrics").text
        # The template should appear exactly once per (method, status)
        # even though three distinct IDs were requested.
        template_lines = [
            l for l in body.splitlines()
            if l.startswith('eduzim_http_requests_total{')
            and 'route="/widgets/{wid}"' in l
            and 'status="200"' in l
        ]
        assert len(template_lines) == 1
        # And the value should be 3.0 (3 calls bucketed together).
        assert template_lines[0].endswith(" 3.0")

    def test_status_codes_separated(self):
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        client.get("/widgets/1")    # 200
        client.get("/widgets/999")  # 404
        body = client.get("/metrics").text
        assert 'status="200"' in body
        assert 'status="404"' in body

    def test_methods_separated(self):
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        client.get("/widgets")
        client.post("/widgets")
        body = client.get("/metrics").text
        get_lines = [l for l in body.splitlines()
                     if 'method="GET"' in l and 'route="/widgets"' in l
                     and l.startswith('eduzim_http_requests_total')]
        post_lines = [l for l in body.splitlines()
                      if 'method="POST"' in l and 'route="/widgets"' in l
                      and l.startswith('eduzim_http_requests_total')]
        assert len(get_lines) >= 1
        assert len(post_lines) >= 1


class TestLatencyHistogram:

    def test_histogram_emitted(self):
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        client.get("/widgets")
        body = client.get("/metrics").text
        assert "# TYPE eduzim_http_request_duration_seconds histogram" in body
        assert "eduzim_http_request_duration_seconds_bucket" in body
        assert "eduzim_http_request_duration_seconds_count" in body
        assert "eduzim_http_request_duration_seconds_sum" in body


class TestServiceLabel:

    def test_service_label_propagates(self):
        app = _build_app()
        metrics.install(app, service_name="my-special-service")
        client = TestClient(app)
        client.get("/widgets")
        body = client.get("/metrics").text
        assert 'service="my-special-service"' in body


class TestUnmatchedRoute:

    def test_unmatched_path_buckets_together(self):
        """404s to random URLs should aggregate under route='unmatched',
        not emit one time series per unique URL."""
        app = _build_app()
        metrics.install(app, service_name="testsvc")
        client = TestClient(app)
        client.get("/this-does-not-exist")
        client.get("/nor-does-this")
        client.get("/random/path/xyz")
        body = client.get("/metrics").text
        # Just one `route="unmatched"` line per status (404 here).
        unmatched_lines = [
            l for l in body.splitlines()
            if 'route="unmatched"' in l
            and l.startswith("eduzim_http_requests_total")
        ]
        # All three 404s collapsed to a single counter line.
        assert len(unmatched_lines) == 1
        assert unmatched_lines[0].endswith(" 3.0")
