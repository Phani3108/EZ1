#!/usr/bin/env python3
"""
Generate the performance report from a load-test run (PH7-4).

Reads:
  * `load_24h_summary.json`  — per-endpoint aggregate stats from load_24h.py
  * `load_24h.csv`           — per-minute time series

Writes:
  * `performance-report.md`  — human-readable summary with tables, p-budget
                                pass/fail per endpoint, and observations.

The report intentionally replaces the marketing version (the audit
called out: "the existing report claims '500-school validated' from a
script that fired 550 mock HTTP requests at localhost — not a real
test"). This generator emits raw numbers from a real run and lets the
operator (or reader) draw conclusions.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# p99 latency BUDGETS per endpoint. Pulled from product expectations:
# parent reads need to feel snappy on a phone; teacher writes can take
# a little longer because they're batched. Bump these as the platform
# matures.
P99_BUDGETS_MS = {
    "teacher_attendance":      500,   # batch write; 200ms of network + DB OK
    "teacher_marks":           500,
    "teacher_announcement":    400,
    "parent_children":         300,
    "parent_student":          300,
    "parent_attendance_trend": 400,
    "parent_feed":             300,
    "parent_fees":             400,
    "admin_dashboard":         800,   # heavier query; budget more
    "admin_attendance_trend":  600,
    "admin_dropout":          1500,   # in-process gather, slowest read
}

ERROR_BUDGET_PCT = 0.5   # any endpoint > 0.5% error rate fails its gate


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate performance-report.md from a load-test run",
    )
    parser.add_argument("--summary", required=True,
                        help="Path to load_24h_summary.json")
    parser.add_argument("--csv", required=True,
                        help="Path to load_24h.csv (per-minute time series)")
    parser.add_argument("--out", required=True,
                        help="Output Markdown report")
    parser.add_argument(
        "--include-grafana-screenshots", default="",
        help="Comma-separated paths to PNG screenshots from Grafana. "
             "Linked in the Observations section.",
    )
    args = parser.parse_args(argv)

    summary_path = Path(args.summary)
    csv_path = Path(args.csv)
    out_path = Path(args.out)

    summary = json.loads(summary_path.read_text())
    minutes = list(_load_csv(csv_path))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render(summary, minutes, args.include_grafana_screenshots))
    print(f"[report] wrote {out_path}", file=sys.stderr)
    return 0


def _load_csv(p: Path) -> list[dict]:
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def _render(summary: dict, minutes: list[dict], screenshots_csv: str) -> str:
    started = summary.get("started_at", "?")
    ended = summary.get("ended_at", "?")
    sizing = summary.get("sizing", {})
    per_endpoint = summary.get("per_endpoint", {})

    duration_hours = _hours_between(started, ended)

    # Compute summary tallies + budget pass/fail
    total_requests = sum(e.get("count", 0) for e in per_endpoint.values())
    total_errors = sum(e.get("errors", 0) for e in per_endpoint.values())
    overall_error_pct = round(100.0 * total_errors / max(1, total_requests), 3)
    peak_rpm = max(
        (int(row["count"]) for row in minutes if row["count"]),
        default=0,
    )

    budget_rows = []
    failures: list[str] = []
    for ep, stats in sorted(per_endpoint.items()):
        budget = P99_BUDGETS_MS.get(ep)
        p99 = stats.get("p99_ms_p99_of_minutes", 0)
        err = stats.get("error_rate_pct", 0)
        budget_pass = (budget is None) or (p99 <= budget)
        error_pass = err <= ERROR_BUDGET_PCT
        overall_pass = budget_pass and error_pass
        status = "✅" if overall_pass else "❌"
        budget_str = f"{budget} ms" if budget else "—"
        if not overall_pass:
            why = []
            if budget and p99 > budget:
                why.append(f"p99 {p99}ms > budget {budget}ms")
            if err > ERROR_BUDGET_PCT:
                why.append(f"errors {err}% > {ERROR_BUDGET_PCT}%")
            failures.append(f"{ep}: {', '.join(why)}")
        budget_rows.append((status, ep, stats.get("count", 0),
                            stats.get("p50_ms_median_of_minutes", 0),
                            stats.get("p95_ms_p95_of_minutes", 0),
                            p99, err, budget_str))

    overall_pass = not failures and overall_error_pct <= ERROR_BUDGET_PCT

    screenshots = [s.strip() for s in screenshots_csv.split(",") if s.strip()]

    return _MD_TEMPLATE.format(
        verdict_emoji="✅ PASSED" if overall_pass else "❌ FAILED",
        started=started,
        ended=ended,
        duration_hours=duration_hours,
        sizing_schools=sizing.get("schools", "?"),
        sizing_students=sizing.get("students_per_school", "?"),
        sizing_teachers=sizing.get("teachers_per_school", "?"),
        total_requests=f"{total_requests:,}",
        total_errors=f"{total_errors:,}",
        overall_error_pct=overall_error_pct,
        peak_rpm=peak_rpm,
        per_endpoint_table=_render_table(budget_rows),
        failures_block=_render_failures(failures, overall_error_pct),
        screenshots_block=_render_screenshots(screenshots),
        budget_legend=_render_budget_legend(),
        generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


def _hours_between(iso_a: str, iso_b: str) -> float:
    try:
        a = datetime.fromisoformat(iso_a.replace("Z", "+00:00"))
        b = datetime.fromisoformat(iso_b.replace("Z", "+00:00"))
        return round((b - a).total_seconds() / 3600.0, 2)
    except Exception:
        return 0.0


def _render_table(rows: list[tuple]) -> str:
    """Endpoint table — markdown."""
    out = [
        "| | endpoint | count | p50 ms | p95 ms | p99 ms | err % | p99 budget |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for status, ep, count, p50, p95, p99, err, budget in rows:
        out.append(
            f"| {status} | `{ep}` | {count:,} | {p50} | {p95} | {p99} | {err} | {budget} |"
        )
    return "\n".join(out)


def _render_failures(failures: list[str], overall_err: float) -> str:
    if not failures and overall_err <= ERROR_BUDGET_PCT:
        return "All endpoints met both their p99 latency budget and the error-rate budget. ✅"
    lines = ["**Failures:**", ""]
    if overall_err > ERROR_BUDGET_PCT:
        lines.append(f"- Overall error rate {overall_err}% exceeds the {ERROR_BUDGET_PCT}% gate.")
    for f in failures:
        lines.append(f"- {f}")
    return "\n".join(lines)


def _render_screenshots(paths: list[str]) -> str:
    if not paths:
        return ("_No Grafana screenshots attached. To include them, pass "
                "`--include-grafana-screenshots a.png,b.png` when generating._")
    out = []
    for p in paths:
        out.append(f"![{p}]({p})")
    return "\n\n".join(out)


def _render_budget_legend() -> str:
    out = ["| endpoint | p99 budget |", "|---|---:|"]
    for k, v in P99_BUDGETS_MS.items():
        out.append(f"| `{k}` | {v} ms |")
    out.append(f"\n_All endpoints share a {ERROR_BUDGET_PCT}% error-rate budget._")
    return "\n".join(out)


_MD_TEMPLATE = """\
# EduZim — Phase 7 Performance Report

**Verdict:** {verdict_emoji}

| | |
|---|---|
| Started | `{started}` |
| Ended | `{ended}` |
| Duration | {duration_hours} hours |
| Seed | {sizing_schools} schools × {sizing_students} students × {sizing_teachers} teachers |
| Total requests | {total_requests} |
| Total errors | {total_errors} |
| Overall error rate | {overall_error_pct}% |
| Peak RPM | {peak_rpm} |

## Per-endpoint results

{per_endpoint_table}

## Pass/fail summary

{failures_block}

## p99 latency budgets

The "p99 budget" column above compares against these per-endpoint
targets. The budgets are product-derived (parent reads need to feel
snappy on a phone; teacher writes can take longer because they're
batched). Bump as the platform matures.

{budget_legend}

## Observations (Grafana)

{screenshots_block}

## Methodology

* Seed: `scripts/load/seed_realistic.py` provisioned the schools listed
  above against the live gateway. Each school has an Admin user (with
  a real login), per-class Teachers (each with a token), Students with
  per-school class enrolment, and Parents linked to their children
  (each with a token).
* Load: `scripts/load/load_24h.py` ran for the duration above. Traffic
  follows a school-day pattern modeled on Zimbabwean schedules
  (06:00–22:00 active, with peak teacher activity 08:00–13:00, parent
  read peak 17:00–22:00).
* No mock traffic: every HTTP call is a real authenticated request
  routed through the gateway → the relevant downstream service →
  Postgres / Kafka / Redis. This replaces the audit-flagged
  `scripts/scale_test.py` (which was 550 mock HTTP calls against
  localhost — not a real test).

## Limitations

* p-values above are computed FROM PER-MINUTE BUCKETS — "p99 of
  minutes" approximates run-wide p99 but doesn't equal it. For exact
  run-wide p-values, query Prometheus directly:
  `histogram_quantile(0.99, sum by (le) (rate(eduzim_http_request_duration_seconds_bucket[24h])))`
* No multi-region testing. Single-region staging deploy only.
* The chaos profile (`docker-compose.chaos.yml`, PH7-2) injects
  5% packet loss + 200ms latency. Production network conditions
  vary — these numbers are conservative for African ISP backbones.

_Report generated `{generated_at}` by `scripts/load/report_generator.py`._
"""


if __name__ == "__main__":
    sys.exit(main())
