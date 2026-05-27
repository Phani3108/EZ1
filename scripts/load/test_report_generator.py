"""Unit tests for the load-test report generator (PH7-4).

The generator is pure-function: input is two files (summary JSON + CSV),
output is one Markdown file. We exercise the budget-comparison logic
and the verdict aggregation since those are the bits a regression
would silently mis-render.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.load import report_generator as rg


def _write_summary(tmp_path: Path, per_endpoint: dict) -> Path:
    p = tmp_path / "summary.json"
    p.write_text(json.dumps({
        "started_at": "2026-05-26T06:00:00+00:00",
        "ended_at":   "2026-05-27T06:00:00+00:00",
        "sizing": {"schools": 500, "students_per_school": 100, "teachers_per_school": 5},
        "per_endpoint": per_endpoint,
    }))
    return p


def _write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "load.csv"
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "endpoint", "count", "errors",
            "p50_ms", "p95_ms", "p99_ms", "error_rate_pct",
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return p


def _all_within_budget() -> dict:
    """A clean run: every endpoint under its budget + zero errors."""
    return {
        "teacher_attendance": {
            "count": 100_000, "errors": 0, "error_rate_pct": 0,
            "p50_ms_median_of_minutes": 120,
            "p95_ms_p95_of_minutes": 300,
            "p99_ms_p99_of_minutes": 450,
            "peak_rpm": 200,
        },
        "parent_children": {
            "count": 50_000, "errors": 5, "error_rate_pct": 0.01,
            "p50_ms_median_of_minutes": 30,
            "p95_ms_p95_of_minutes": 100,
            "p99_ms_p99_of_minutes": 250,
            "peak_rpm": 100,
        },
    }


class TestHappyPath:

    def test_clean_run_verdict_is_passed(self, tmp_path):
        summary = _write_summary(tmp_path, _all_within_budget())
        csv_path = _write_csv(tmp_path, [
            {"timestamp": "2026-05-26T08:00:00Z", "endpoint": "teacher_attendance",
             "count": 100, "errors": 0,
             "p50_ms": 100, "p95_ms": 200, "p99_ms": 300, "error_rate_pct": 0},
        ])
        out = tmp_path / "report.md"
        rc = rg.main(["--summary", str(summary),
                      "--csv", str(csv_path),
                      "--out", str(out)])
        assert rc == 0
        body = out.read_text()
        assert "✅ PASSED" in body
        assert "✅ | `teacher_attendance`" in body
        assert "✅ | `parent_children`" in body

    def test_report_includes_sizing(self, tmp_path):
        summary = _write_summary(tmp_path, _all_within_budget())
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out)])
        body = out.read_text()
        assert "500 schools × 100 students × 5 teachers" in body

    def test_report_includes_duration(self, tmp_path):
        summary = _write_summary(tmp_path, _all_within_budget())
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out)])
        body = out.read_text()
        assert "24.0 hours" in body


class TestBudgetFailures:

    def test_p99_over_budget_fails(self, tmp_path):
        """teacher_attendance budget is 500ms; report should fail it
        when p99 reaches 800ms."""
        summary = _write_summary(tmp_path, {
            "teacher_attendance": {
                "count": 1000, "errors": 0, "error_rate_pct": 0,
                "p50_ms_median_of_minutes": 100,
                "p95_ms_p95_of_minutes": 400,
                "p99_ms_p99_of_minutes": 800,   # over budget
                "peak_rpm": 50,
            },
        })
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out)])
        body = out.read_text()
        assert "❌ FAILED" in body
        assert "❌ | `teacher_attendance`" in body
        assert "p99 800ms > budget 500ms" in body

    def test_error_rate_over_budget_fails(self, tmp_path):
        """Any endpoint > 0.5% error rate is a fail, even with good p99."""
        summary = _write_summary(tmp_path, {
            "parent_feed": {
                "count": 10_000, "errors": 100, "error_rate_pct": 1.0,
                "p50_ms_median_of_minutes": 50,
                "p95_ms_p95_of_minutes": 100,
                "p99_ms_p99_of_minutes": 200,
                "peak_rpm": 100,
            },
        })
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out)])
        body = out.read_text()
        assert "❌ FAILED" in body
        assert "errors 1.0% > 0.5%" in body

    def test_multiple_failures_listed(self, tmp_path):
        summary = _write_summary(tmp_path, {
            "teacher_attendance": {
                "count": 1000, "errors": 0, "error_rate_pct": 0,
                "p50_ms_median_of_minutes": 100,
                "p95_ms_p95_of_minutes": 400,
                "p99_ms_p99_of_minutes": 900,    # over budget
                "peak_rpm": 50,
            },
            "parent_feed": {
                "count": 10_000, "errors": 100, "error_rate_pct": 1.0,
                "p50_ms_median_of_minutes": 50,
                "p95_ms_p95_of_minutes": 100,
                "p99_ms_p99_of_minutes": 200,
                "peak_rpm": 100,
            },
        })
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out)])
        body = out.read_text()
        assert "teacher_attendance:" in body
        assert "parent_feed:" in body


class TestUnknownEndpoint:

    def test_unknown_endpoint_no_budget(self, tmp_path):
        """A new endpoint not in P99_BUDGETS_MS should be reported
        without a budget column AND should not be marked as failing."""
        summary = _write_summary(tmp_path, {
            "novel_endpoint": {
                "count": 100, "errors": 0, "error_rate_pct": 0,
                "p50_ms_median_of_minutes": 50,
                "p95_ms_p95_of_minutes": 100,
                "p99_ms_p99_of_minutes": 5000,    # would fail any reasonable budget
                "peak_rpm": 10,
            },
        })
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out)])
        body = out.read_text()
        assert "✅ | `novel_endpoint`" in body
        assert "| — |" in body  # no budget
        # Overall verdict should still PASS (no known-budget violations + no errors).
        assert "✅ PASSED" in body


class TestGrafanaScreenshots:

    def test_screenshots_linked_when_provided(self, tmp_path):
        summary = _write_summary(tmp_path, _all_within_budget())
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out),
                 "--include-grafana-screenshots", "a.png,b.png"])
        body = out.read_text()
        assert "![a.png](a.png)" in body
        assert "![b.png](b.png)" in body

    def test_screenshots_block_explains_when_missing(self, tmp_path):
        summary = _write_summary(tmp_path, _all_within_budget())
        csv_path = _write_csv(tmp_path, [])
        out = tmp_path / "report.md"
        rg.main(["--summary", str(summary),
                 "--csv", str(csv_path),
                 "--out", str(out)])
        body = out.read_text()
        assert "No Grafana screenshots attached" in body
