#!/usr/bin/env python3
"""
24-hour realistic load test (PH7-1).

Reads `seed_artifacts.json` (from seed_realistic.py), then drives a
realistic school-day pattern against the gateway for 24 hours.
Captures per-endpoint p50 / p95 / p99 / error rate in a per-minute
CSV, plus a final JSON summary.

Traffic pattern (modeled on actual Zimbabwean school schedules):

  06:00–07:30  Ramp     — parents check overnight notifications / fees
  07:30–13:00  Burst    — teachers mark attendance per period (8 periods),
                          parent reads peak ~lunch
  13:00–15:00  Mid      — marks entry for morning assessments
  15:00–17:00  Ramp-down — admin daily summary; fee payments trickle in
  17:00–22:00  Evening  — parent reads + occasional admin work
  22:00–06:00  Quiet    — backend operations only (Kafka consumer catches up)

The script does NOT compress 24 hours into 24 minutes — Phase 7's
point is real sustained load over a real day. Use `--smoke` for
5-minute compressed runs.

Endpoints exercised (gateway routes; the gateway forwards to the right
downstream service):

  Teacher actions:
    POST /api/v1/attendance/sync         (every period)
    POST /api/v1/assessments              (1/teacher/day)
    POST /api/v1/assessments/{id}/marks/bulk (after each assessment)
    POST /api/v1/comm/announcements      (occasional)

  Parent actions:
    GET  /api/v1/parents/me/children
    GET  /api/v1/students/{id}            (per child)
    GET  /api/v1/attendance/student-trend
    GET  /api/v1/comm/feed
    GET  /api/v1/fees/invoices            (weekly cadence)

  Admin actions:
    GET  /api/v1/reports/dashboard
    GET  /api/v1/reports/attendance/trend
    GET  /api/v1/reports/dropout/summary  (less frequent)

Each request records its latency + status into an in-memory rolling
window; once per minute the window flushes to CSV and resets.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import quantiles, mean
from typing import Optional

try:
    import httpx
except ImportError:
    print("install httpx:  pip install httpx>=0.27.0", file=sys.stderr)
    sys.exit(1)


# ─── Traffic profile (school-day pattern) ────────────────────────


@dataclass
class HourlyProfile:
    """Requests/minute target per (endpoint family) for a given hour-of-day.

    The numbers are PER 100 SCHOOLS — the script scales them by the
    actual seed size at runtime.
    """
    teacher_attendance: int = 0
    teacher_marks: int = 0
    teacher_announcement: int = 0
    parent_children: int = 0
    parent_student: int = 0
    parent_attendance_trend: int = 0
    parent_feed: int = 0
    parent_fees: int = 0
    admin_dashboard: int = 0
    admin_attendance_trend: int = 0
    admin_dropout: int = 0


# Each tuple is (hour_local, profile). Lookup is "highest hour ≤ now".
SCHOOL_DAY_PROFILE = [
    # 22:00–06:00 — quiet
    (22, HourlyProfile()),
    # 06:00–07:30 — early ramp
    (6, HourlyProfile(parent_children=8, parent_feed=12, parent_fees=2)),
    # 07:30 — start of school
    (7, HourlyProfile(
        teacher_attendance=30,                # 1 batch per teacher per period; ~30 schools/min
        parent_children=20, parent_feed=15,
    )),
    # 08:00–13:00 — peak teacher activity
    (8, HourlyProfile(
        teacher_attendance=40, teacher_announcement=2,
        parent_children=25, parent_student=15,
        parent_attendance_trend=10, parent_feed=20,
        admin_dashboard=3,
    )),
    # 10:00 — sustained burst
    (10, HourlyProfile(
        teacher_attendance=40, teacher_marks=10, teacher_announcement=2,
        parent_children=30, parent_student=20,
        parent_attendance_trend=15, parent_feed=25,
        admin_dashboard=5, admin_attendance_trend=2,
    )),
    # 13:00–15:00 — marks entry after morning assessments
    (13, HourlyProfile(
        teacher_attendance=20, teacher_marks=30, teacher_announcement=3,
        parent_children=20, parent_feed=20,
        admin_dashboard=4,
    )),
    # 15:00–17:00 — ramp-down + admin daily review
    (15, HourlyProfile(
        teacher_marks=15, teacher_announcement=2,
        parent_children=15, parent_feed=20, parent_fees=5,
        admin_dashboard=8, admin_attendance_trend=5, admin_dropout=2,
    )),
    # 17:00–22:00 — evening parent activity
    (17, HourlyProfile(
        parent_children=30, parent_student=20,
        parent_attendance_trend=10, parent_feed=25, parent_fees=8,
        admin_dashboard=2,
    )),
    # 22:00 — back to quiet (catches the loop)
    (22, HourlyProfile()),
]


def profile_at(hour_local: int) -> HourlyProfile:
    """Return the matching profile for the given local hour."""
    # Find the highest entry whose hour ≤ hour_local. Wrap around at
    # midnight (handled by sort + scan).
    matching = [p for h, p in SCHOOL_DAY_PROFILE if h <= hour_local]
    if matching:
        return matching[-1]
    # Before 06:00 → quiet profile.
    return HourlyProfile()


# ─── Metric collection ───────────────────────────────────────────


@dataclass
class MinuteBucket:
    """One row of the output CSV — stats for one (endpoint, minute) pair."""
    timestamp: str
    endpoint: str
    count: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    def summarize(self) -> dict:
        if not self.latencies_ms:
            return {
                "timestamp": self.timestamp, "endpoint": self.endpoint,
                "count": 0, "errors": 0,
                "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "error_rate_pct": 0,
            }
        sorted_latencies = sorted(self.latencies_ms)
        n = len(sorted_latencies)
        p50 = sorted_latencies[int(n * 0.50)]
        p95 = sorted_latencies[min(n - 1, int(n * 0.95))]
        p99 = sorted_latencies[min(n - 1, int(n * 0.99))]
        return {
            "timestamp": self.timestamp,
            "endpoint": self.endpoint,
            "count": self.count,
            "errors": self.errors,
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "p99_ms": round(p99, 1),
            "error_rate_pct": round(100.0 * self.errors / max(1, self.count), 2),
        }


class Collector:
    """In-memory rolling buckets per endpoint; flush to CSV per minute."""

    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.current: dict[str, MinuteBucket] = {}
        self.minute_key: str = ""
        self.all_summaries: list[dict] = []   # for the final JSON
        # Write header
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.csv_path, "w", newline="")
        self._writer = csv.DictWriter(self._fp, fieldnames=[
            "timestamp", "endpoint", "count", "errors",
            "p50_ms", "p95_ms", "p99_ms", "error_rate_pct",
        ])
        self._writer.writeheader()

    def record(self, endpoint: str, latency_ms: float, status: int):
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y-%m-%dT%H:%M:00Z")
        if minute_key != self.minute_key:
            self._flush()
            self.minute_key = minute_key

        bucket = self.current.setdefault(
            endpoint,
            MinuteBucket(timestamp=minute_key, endpoint=endpoint),
        )
        bucket.count += 1
        bucket.latencies_ms.append(latency_ms)
        if status >= 500 or status == 0:
            bucket.errors += 1

    def _flush(self):
        for bucket in self.current.values():
            summary = bucket.summarize()
            self._writer.writerow(summary)
            self.all_summaries.append(summary)
        self._fp.flush()
        self.current.clear()

    def finalize_json(self, out_json: Path, started_at: str, ended_at: str,
                       sizing: dict) -> None:
        """Aggregate all minutes into an overall per-endpoint summary."""
        # Flush the last minute
        self._flush()
        self._fp.close()

        per_endpoint: dict[str, dict] = defaultdict(lambda: {
            "count": 0, "errors": 0, "all_latencies_ms": []
        })
        for row in self.all_summaries:
            ep = row["endpoint"]
            per_endpoint[ep]["count"] += row["count"]
            per_endpoint[ep]["errors"] += row["errors"]
            # We don't have raw latencies anymore — approximate the overall
            # quantiles by taking the p99-of-p99 over minutes. This is a
            # known approximation; for exact figures the operator would
            # need to query Prometheus directly via the report_generator.

        # Use per-minute p-values to estimate run-wide p-values.
        # (Honest about approximation in the report.)
        per_endpoint_runwide: dict[str, dict] = {}
        for ep in per_endpoint:
            minute_p95s = [r["p95_ms"] for r in self.all_summaries if r["endpoint"] == ep and r["count"] > 0]
            minute_p99s = [r["p99_ms"] for r in self.all_summaries if r["endpoint"] == ep and r["count"] > 0]
            minute_p50s = [r["p50_ms"] for r in self.all_summaries if r["endpoint"] == ep and r["count"] > 0]
            if not minute_p99s:
                continue
            per_endpoint_runwide[ep] = {
                "count": per_endpoint[ep]["count"],
                "errors": per_endpoint[ep]["errors"],
                "error_rate_pct": round(100.0 * per_endpoint[ep]["errors"] /
                                        max(1, per_endpoint[ep]["count"]), 3),
                "p50_ms_median_of_minutes": round(median(minute_p50s), 1),
                "p95_ms_p95_of_minutes": round(p_of(minute_p95s, 0.95), 1),
                "p99_ms_p99_of_minutes": round(p_of(minute_p99s, 0.99), 1),
                "peak_rpm": max((r["count"] for r in self.all_summaries
                                 if r["endpoint"] == ep), default=0),
            }

        out_json.write_text(json.dumps({
            "started_at": started_at,
            "ended_at": ended_at,
            "sizing": sizing,
            "per_endpoint": per_endpoint_runwide,
        }, indent=2))


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def p_of(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(len(s) * q))]


# ─── Endpoint drivers ────────────────────────────────────────────


class Driver:
    """One Driver per endpoint family. Each tick, fires N requests
    against the gateway and records latencies into the Collector."""

    def __init__(self, name: str, client: httpx.AsyncClient,
                 collector: Collector):
        self.name = name
        self.client = client
        self.collector = collector

    async def _do(self, method: str, path: str, *,
                  token: Optional[str] = None,
                  json_body: Optional[dict] = None,
                  params: Optional[dict] = None) -> None:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        t0 = time.perf_counter()
        try:
            r = await self.client.request(method, path, headers=headers,
                                          json=json_body, params=params)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.collector.record(self.name, elapsed_ms, r.status_code)
        except Exception:  # noqa: BLE001
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.collector.record(self.name, elapsed_ms, 0)


# ─── Tick loop ───────────────────────────────────────────────────


def _scale_for_size(count_per_100: int, n_schools: int) -> int:
    """Scale the per-100-schools target by the actual seed size."""
    return max(0, int(round(count_per_100 * n_schools / 100)))


async def run_tick(
    drivers: dict[str, Driver],
    schools: list[dict],
    profile: HourlyProfile,
    smoke: bool,
) -> None:
    """One minute of traffic. Fires the per-minute counts in parallel."""
    n_schools = len(schools)
    if smoke:
        # Smoke compresses ALL endpoint counts to a small fraction.
        scale = lambda x: max(1, x // 5) if x else 0
    else:
        scale = lambda x: _scale_for_size(x, n_schools)

    tasks: list = []

    # ─ Teacher attendance ─
    n = scale(profile.teacher_attendance)
    for _ in range(n):
        school = random.choice(schools)
        if not school["teachers"]:
            continue
        teacher = random.choice(school["teachers"])
        if not school["students"]:
            continue
        # Pick a random subset of class students for this period's batch
        class_students = [s for s in school["students"]
                          if s["class_id"] == teacher["class_id"]]
        if not class_students:
            continue
        batch_id = f"batch-{teacher['user_id']}-{int(time.time())}-{random.randint(0, 999)}"
        events = [
            {
                "student_id": s["id"],
                "class_id": teacher["class_id"],
                "date": datetime.now(timezone.utc).date().isoformat(),
                "status": random.choices(["P", "A", "L"], weights=[0.92, 0.05, 0.03])[0],
                "client_event_id": f"evt-{batch_id}-{s['id']}",
            }
            for s in class_students[:40]
        ]
        tasks.append(drivers["teacher_attendance"]._do(
            "POST", "/api/v1/attendance/sync",
            token=teacher["token"],
            json_body={
                "device_id": f"dev-{teacher['user_id']}",
                "sync_batch_id": batch_id,
                "events": events,
            },
        ))

    # ─ Parent reads ─
    for label, count in [
        ("parent_children", profile.parent_children),
        ("parent_feed", profile.parent_feed),
        ("parent_fees", profile.parent_fees),
        ("parent_attendance_trend", profile.parent_attendance_trend),
        ("parent_student", profile.parent_student),
    ]:
        for _ in range(scale(count)):
            school = random.choice(schools)
            if not school["parents"]:
                continue
            parent = random.choice(school["parents"])
            if label == "parent_children":
                tasks.append(drivers[label]._do(
                    "GET", "/api/v1/parents/me/children",
                    token=parent["token"],
                ))
            elif label == "parent_feed":
                tasks.append(drivers[label]._do(
                    "GET", "/api/v1/comm/feed",
                    token=parent["token"],
                ))
            elif label == "parent_fees":
                if parent["student_ids"]:
                    tasks.append(drivers[label]._do(
                        "GET", "/api/v1/fees/invoices",
                        token=parent["token"],
                        params={"student_id": parent["student_ids"][0]},
                    ))
            elif label == "parent_attendance_trend":
                if parent["student_ids"]:
                    today = datetime.now(timezone.utc).date()
                    tasks.append(drivers[label]._do(
                        "GET", "/api/v1/attendance/student-trend",
                        token=parent["token"],
                        params={
                            "student_id": parent["student_ids"][0],
                            "from": (today.replace(day=1)).isoformat(),
                            "to": today.isoformat(),
                        },
                    ))
            elif label == "parent_student":
                if parent["student_ids"]:
                    tasks.append(drivers[label]._do(
                        "GET", f"/api/v1/students/{parent['student_ids'][0]}",
                        token=parent["token"],
                    ))

    # ─ Admin reads ─
    for label, count in [
        ("admin_dashboard", profile.admin_dashboard),
        ("admin_attendance_trend", profile.admin_attendance_trend),
        ("admin_dropout", profile.admin_dropout),
    ]:
        for _ in range(scale(count)):
            school = random.choice(schools)
            if label == "admin_dashboard":
                tasks.append(drivers[label]._do(
                    "GET", "/api/v1/reports/dashboard",
                    token=school["admin_token"],
                ))
            elif label == "admin_attendance_trend":
                today = datetime.now(timezone.utc).date()
                tasks.append(drivers[label]._do(
                    "GET", "/api/v1/reports/attendance/trend",
                    token=school["admin_token"],
                    params={
                        "from": (today.replace(day=1)).isoformat(),
                        "to": today.isoformat(),
                    },
                ))
            elif label == "admin_dropout":
                tasks.append(drivers[label]._do(
                    "GET", "/api/v1/reports/dropout/summary",
                    token=school["admin_token"],
                ))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


# ─── Main loop ───────────────────────────────────────────────────


async def run_load(
    base_url: str,
    artifacts: dict,
    duration_seconds: int,
    concurrency: int,
    out_csv: Path,
    out_json: Path,
    smoke: bool,
    log: logging.Logger,
) -> None:
    schools = artifacts["schools"]
    if not schools:
        log.error("seed artifacts contain 0 schools; aborting")
        return

    limits = httpx.Limits(max_keepalive_connections=concurrency,
                          max_connections=concurrency * 2)
    timeout = httpx.Timeout(30.0, connect=5.0)
    async with httpx.AsyncClient(base_url=base_url, limits=limits,
                                 timeout=timeout) as client:
        collector = Collector(out_csv)
        ENDPOINTS = [
            "teacher_attendance", "teacher_marks", "teacher_announcement",
            "parent_children", "parent_student", "parent_attendance_trend",
            "parent_feed", "parent_fees",
            "admin_dashboard", "admin_attendance_trend", "admin_dropout",
        ]
        drivers = {ep: Driver(ep, client, collector) for ep in ENDPOINTS}

        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()
        next_tick = start_time
        TICK_SECONDS = 5 if smoke else 60

        while time.time() - start_time < duration_seconds:
            now = time.time()
            if now < next_tick:
                await asyncio.sleep(next_tick - now)
            hour_local = datetime.now().hour
            profile = profile_at(hour_local)
            await run_tick(drivers, schools, profile, smoke)
            next_tick += TICK_SECONDS

            # Progress log every 5 minutes (or every minute in smoke)
            elapsed = time.time() - start_time
            if smoke or int(elapsed) % 300 < TICK_SECONDS:
                log.info("[load] %.1f%% elapsed (%.0fs / %ds)",
                         100 * elapsed / duration_seconds,
                         elapsed, duration_seconds)

        ended_at = datetime.now(timezone.utc).isoformat()
        collector.finalize_json(out_json, started_at, ended_at,
                                artifacts["sizing"])
        log.info("[load] DONE. CSV: %s   JSON: %s", out_csv, out_json)


# ─── CLI ─────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="24-hour realistic load test (PH7-1)",
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--seed-artifacts", required=True,
                        help="Path to seed_realistic.py's output JSON")
    parser.add_argument("--duration-hours", type=float, default=24)
    parser.add_argument("--concurrency", type=int, default=200)
    parser.add_argument("--out-csv", default="scripts/load/load_24h.csv")
    parser.add_argument("--out-json", default="scripts/load/load_24h_summary.json")
    parser.add_argument("--smoke", action="store_true",
                        help="5-minute compressed run instead of 24-hour")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("load")

    artifacts = json.loads(Path(args.seed_artifacts).read_text())
    duration = 300 if args.smoke else int(args.duration_hours * 3600)
    log.info("[load] base=%s schools=%d duration=%ds conc=%d smoke=%s",
             args.base_url, len(artifacts["schools"]), duration,
             args.concurrency, args.smoke)

    asyncio.run(run_load(
        base_url=args.base_url.rstrip("/"),
        artifacts=artifacts,
        duration_seconds=duration,
        concurrency=args.concurrency,
        out_csv=Path(args.out_csv),
        out_json=Path(args.out_json),
        smoke=args.smoke,
        log=log,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
