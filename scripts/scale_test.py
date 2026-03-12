#!/usr/bin/env python3
"""
EduZim Scale Simulation — 500 Schools × 100 Students
======================================================
Simulates realistic concurrent load against the EduZim API gateway
to verify the system can handle Zimbabwe MoPSE-scale traffic.

Profiles simulated:
  - Attendance sync: teachers batch-posting attendance for 40-student classes
  - Marks bulk upsert: teachers uploading assessment marks with idempotency
  - Announcement creation: teachers sending class announcements
  - Parent feed reads: parents checking their child's feed

Metrics collected:
  - Throughput (requests/sec)
  - Latency p50 / p95 / p99
  - Error rate
  - Idempotency replay correctness

Usage:
  python scripts/scale_test.py [--base-url http://localhost:8000] [--schools 500] [--students-per-school 100]
"""

import argparse
import asyncio
import json
import os
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("Install httpx:  pip install httpx")
    raise SystemExit(1)


# ─── Configuration ───────────────────────────────────────────────

@dataclass
class SimConfig:
    base_url: str = "http://localhost:8000"
    num_schools: int = 500
    students_per_school: int = 100
    classes_per_school: int = 5
    students_per_class: int = 40
    concurrency: int = 50
    attendance_batches: int = 200       # total attendance POST requests
    marks_batches: int = 200            # total marks POST requests
    announcement_sends: int = 100       # total announcement requests
    parent_feed_reads: int = 200        # total feed GET requests
    idempotency_replays: int = 50       # duplicate requests to test
    timeout: float = 30.0


# ─── Metric Collector ────────────────────────────────────────────

@dataclass
class Metrics:
    latencies: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    status_codes: dict = field(default_factory=lambda: {})
    idempotency_hits: int = 0
    idempotency_misses: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    def record(self, latency_ms: float, status: int, error: str = None):
        self.latencies.append(latency_ms)
        self.status_codes[status] = self.status_codes.get(status, 0) + 1
        if error:
            self.errors.append(error)

    def summary(self) -> dict:
        if not self.latencies:
            return {"total_requests": 0}
        sorted_lat = sorted(self.latencies)
        n = len(sorted_lat)
        duration = self.end_time - self.start_time
        return {
            "total_requests": n,
            "duration_sec": round(duration, 2),
            "throughput_rps": round(n / duration, 1) if duration > 0 else 0,
            "latency_p50_ms": round(sorted_lat[int(n * 0.50)], 1),
            "latency_p95_ms": round(sorted_lat[int(n * 0.95)], 1),
            "latency_p99_ms": round(sorted_lat[int(n * 0.99)], 1),
            "latency_mean_ms": round(statistics.mean(sorted_lat), 1),
            "latency_max_ms": round(max(sorted_lat), 1),
            "error_count": len(self.errors),
            "error_rate_pct": round(len(self.errors) / n * 100, 2),
            "status_codes": dict(sorted(self.status_codes.items())),
            "idempotency_hits": self.idempotency_hits,
            "idempotency_misses": self.idempotency_misses,
        }


# ─── Fake Data Generators ───────────────────────────────────────

def fake_school_id(i: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"school-{i}"))

def fake_student_id(school_idx: int, student_idx: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"student-{school_idx}-{student_idx}"))

def fake_class_id(school_idx: int, class_idx: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"class-{school_idx}-{class_idx}"))

def fake_teacher_id(school_idx: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"teacher-{school_idx}"))

def fake_assessment_id(school_idx: int, class_idx: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"assessment-{school_idx}-{class_idx}"))

def fake_jwt(school_idx: int, role: str = "Teacher") -> str:
    """Generate a mock JWT header value (gateway test mode accepts these)."""
    return f"Bearer test-token-school{school_idx}-{role.lower()}"


def gen_attendance_payload(cfg: SimConfig) -> tuple[dict, dict]:
    """Return (headers, body) for an attendance sync request."""
    school_idx = random.randint(0, cfg.num_schools - 1)
    class_idx = random.randint(0, cfg.classes_per_school - 1)
    school_id = fake_school_id(school_idx)
    class_id = fake_class_id(school_idx, class_idx)
    device_id = f"device-{school_idx}-{random.randint(0, 9)}"
    sync_batch_id = str(uuid.uuid4())

    events = []
    for s in range(cfg.students_per_class):
        events.append({
            "student_id": fake_student_id(school_idx, s),
            "status": random.choice(["PRESENT", "PRESENT", "PRESENT", "ABSENT", "LATE"]),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

    headers = {
        "Authorization": fake_jwt(school_idx),
        "X-School-Id": school_id,
        "X-Request-Id": sync_batch_id,
        "Content-Type": "application/json",
    }
    body = {
        "class_id": class_id,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "device_id": device_id,
        "sync_batch_id": sync_batch_id,
        "events": events,
    }
    return headers, body


def gen_marks_payload(cfg: SimConfig) -> tuple[dict, dict]:
    """Return (headers, body) for a marks bulk-upsert request."""
    school_idx = random.randint(0, cfg.num_schools - 1)
    class_idx = random.randint(0, cfg.classes_per_school - 1)
    school_id = fake_school_id(school_idx)
    assessment_id = fake_assessment_id(school_idx, class_idx)
    request_id = str(uuid.uuid4())

    marks = []
    for s in range(cfg.students_per_class):
        marks.append({
            "student_id": fake_student_id(school_idx, s),
            "score": round(random.uniform(20, 100), 1),
            "grade": random.choice(["A", "B", "C", "D", "E"]),
            "comment": "Good effort" if random.random() > 0.5 else "",
        })

    headers = {
        "Authorization": fake_jwt(school_idx),
        "X-School-Id": school_id,
        "X-Request-Id": request_id,
        "Content-Type": "application/json",
    }
    body = {"marks": marks}
    return headers, body, assessment_id, request_id


def gen_announcement_payload(cfg: SimConfig) -> tuple[dict, dict]:
    """Return (headers, body) for an announcement creation request."""
    school_idx = random.randint(0, cfg.num_schools - 1)
    school_id = fake_school_id(school_idx)
    class_idx = random.randint(0, cfg.classes_per_school - 1)
    request_id = str(uuid.uuid4())

    headers = {
        "Authorization": fake_jwt(school_idx),
        "X-School-Id": school_id,
        "X-Request-Id": request_id,
        "Content-Type": "application/json",
    }
    body = {
        "title": f"Important Notice — {random.choice(['Exam Schedule', 'Sports Day', 'PTA Meeting', 'Holiday', 'Fee Reminder'])}",
        "body": "Please take note of the following important information regarding your child's school activities.",
        "audience": {
            "type": random.choice(["ALL", "CLASS"]),
            "class_id": str(fake_class_id(school_idx, class_idx)),
        },
        "channels": ["IN_APP"],
    }
    return headers, body, request_id


def gen_feed_params(cfg: SimConfig) -> tuple[dict, dict]:
    """Return (headers, query_params) for a parent feed request."""
    school_idx = random.randint(0, cfg.num_schools - 1)
    student_idx = random.randint(0, min(cfg.students_per_school, cfg.students_per_class) - 1)
    school_id = fake_school_id(school_idx)
    student_id = fake_student_id(school_idx, student_idx)

    headers = {
        "Authorization": fake_jwt(school_idx, "Parent"),
        "X-School-Id": school_id,
    }
    params = {"student_id": student_id, "page": 1, "page_size": 20}
    return headers, params


# ─── Request Workers ─────────────────────────────────────────────

async def post_attendance(client: httpx.AsyncClient, cfg: SimConfig, metrics: Metrics):
    headers, body = gen_attendance_payload(cfg)
    url = f"{cfg.base_url}/api/v1/attendance/sync"
    t0 = time.monotonic()
    try:
        resp = await client.post(url, json=body, headers=headers, timeout=cfg.timeout)
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, resp.status_code)
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, 0, str(e))


async def post_marks(client: httpx.AsyncClient, cfg: SimConfig, metrics: Metrics):
    headers, body, assessment_id, _ = gen_marks_payload(cfg)
    url = f"{cfg.base_url}/api/v1/assessments/{assessment_id}/marks/bulk"
    t0 = time.monotonic()
    try:
        resp = await client.post(url, json=body, headers=headers, timeout=cfg.timeout)
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, resp.status_code)
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, 0, str(e))


async def post_announcement(client: httpx.AsyncClient, cfg: SimConfig, metrics: Metrics):
    headers, body, _ = gen_announcement_payload(cfg)
    url = f"{cfg.base_url}/api/v1/comm/announcements"
    t0 = time.monotonic()
    try:
        resp = await client.post(url, json=body, headers=headers, timeout=cfg.timeout)
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, resp.status_code)
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, 0, str(e))


async def get_feed(client: httpx.AsyncClient, cfg: SimConfig, metrics: Metrics):
    headers, params = gen_feed_params(cfg)
    url = f"{cfg.base_url}/api/v1/comm/feed"
    t0 = time.monotonic()
    try:
        resp = await client.get(url, headers=headers, params=params, timeout=cfg.timeout)
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, resp.status_code)
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, 0, str(e))


async def replay_marks_idempotent(client: httpx.AsyncClient, cfg: SimConfig, metrics: Metrics):
    """Send the same marks request twice with the same X-Request-Id to verify idempotency."""
    headers, body, assessment_id, request_id = gen_marks_payload(cfg)
    url = f"{cfg.base_url}/api/v1/assessments/{assessment_id}/marks/bulk"

    # First send
    try:
        await client.post(url, json=body, headers=headers, timeout=cfg.timeout)
    except Exception:
        pass

    # Replay with same X-Request-Id
    t0 = time.monotonic()
    try:
        resp = await client.post(url, json=body, headers=headers, timeout=cfg.timeout)
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data", {}).get("already_processed"):
                metrics.idempotency_hits += 1
            else:
                metrics.idempotency_misses += 1
    except Exception as e:
        latency = (time.monotonic() - t0) * 1000
        metrics.record(latency, 0, str(e))
        metrics.idempotency_misses += 1


# ─── Orchestrator ────────────────────────────────────────────────

async def run_simulation(cfg: SimConfig):
    print(f"\n{'='*60}")
    print(f"  EduZim Scale Simulation")
    print(f"  {cfg.num_schools} schools × {cfg.students_per_school} students")
    print(f"  Target: {cfg.base_url}")
    print(f"  Concurrency: {cfg.concurrency}")
    print(f"{'='*60}\n")

    metrics = Metrics()
    semaphore = asyncio.Semaphore(cfg.concurrency)

    async def bounded(coro):
        async with semaphore:
            await coro

    # Build task queue: mix of all request types
    tasks = []
    async with httpx.AsyncClient() as client:
        for _ in range(cfg.attendance_batches):
            tasks.append(bounded(post_attendance(client, cfg, metrics)))
        for _ in range(cfg.marks_batches):
            tasks.append(bounded(post_marks(client, cfg, metrics)))
        for _ in range(cfg.announcement_sends):
            tasks.append(bounded(post_announcement(client, cfg, metrics)))
        for _ in range(cfg.parent_feed_reads):
            tasks.append(bounded(get_feed(client, cfg, metrics)))
        for _ in range(cfg.idempotency_replays):
            tasks.append(bounded(replay_marks_idempotent(client, cfg, metrics)))

        # Shuffle to simulate realistic interleaved traffic
        random.shuffle(tasks)

        print(f"Launching {len(tasks)} requests...\n")
        metrics.start_time = time.monotonic()
        await asyncio.gather(*tasks, return_exceptions=True)
        metrics.end_time = time.monotonic()

    return metrics


def generate_report(cfg: SimConfig, metrics: Metrics) -> str:
    s = metrics.summary()
    lines = [
        "# EduZim Scale Simulation Report",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Configuration",
        "",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Schools | {cfg.num_schools} |",
        f"| Students/school | {cfg.students_per_school} |",
        f"| Total student population | {cfg.num_schools * cfg.students_per_school:,} |",
        f"| Classes/school | {cfg.classes_per_school} |",
        f"| Concurrency | {cfg.concurrency} |",
        f"| Attendance batches | {cfg.attendance_batches} |",
        f"| Marks batches | {cfg.marks_batches} |",
        f"| Announcement sends | {cfg.announcement_sends} |",
        f"| Parent feed reads | {cfg.parent_feed_reads} |",
        f"| Idempotency replays | {cfg.idempotency_replays} |",
        "",
        "## Results",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total requests | {s.get('total_requests', 0)} |",
        f"| Duration | {s.get('duration_sec', 0)}s |",
        f"| Throughput | {s.get('throughput_rps', 0)} req/s |",
        f"| Latency p50 | {s.get('latency_p50_ms', 0)}ms |",
        f"| Latency p95 | {s.get('latency_p95_ms', 0)}ms |",
        f"| Latency p99 | {s.get('latency_p99_ms', 0)}ms |",
        f"| Latency mean | {s.get('latency_mean_ms', 0)}ms |",
        f"| Latency max | {s.get('latency_max_ms', 0)}ms |",
        f"| Error count | {s.get('error_count', 0)} |",
        f"| Error rate | {s.get('error_rate_pct', 0)}% |",
        "",
        "## Status Code Distribution",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for code, count in sorted(s.get("status_codes", {}).items()):
        lines.append(f"| {code} | {count} |")

    lines += [
        "",
        "## Idempotency Verification",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Replay attempts | {cfg.idempotency_replays} |",
        f"| Correctly de-duplicated | {s.get('idempotency_hits', 0)} |",
        f"| Missed (processed twice) | {s.get('idempotency_misses', 0)} |",
        f"| Hit rate | {round(s.get('idempotency_hits', 0) / max(cfg.idempotency_replays, 1) * 100, 1)}% |",
        "",
        "## Quality Gate",
        "",
    ]

    # Quality checks
    checks = []
    throughput = s.get("throughput_rps", 0)
    p95 = s.get("latency_p95_ms", 999999)
    error_rate = s.get("error_rate_pct", 100)
    idem_rate = s.get("idempotency_hits", 0) / max(cfg.idempotency_replays, 1) * 100

    checks.append(("Throughput > 50 req/s", throughput > 50))
    checks.append(("p95 latency < 2000ms", p95 < 2000))
    checks.append(("Error rate < 5%", error_rate < 5))
    checks.append(("Idempotency hit rate > 90%", idem_rate > 90))

    lines.append("| Check | Status |")
    lines.append("|-------|--------|")
    all_pass = True
    for label, passed in checks:
        icon = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        lines.append(f"| {label} | {icon} |")

    lines += [
        "",
        f"**Overall: {'PASS' if all_pass else 'FAIL'}**",
        "",
        "---",
        f"*Generated by EduZim scale_test.py — {cfg.num_schools} schools simulation*",
    ]
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="EduZim Scale Simulation")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API gateway URL")
    parser.add_argument("--schools", type=int, default=500, help="Number of schools")
    parser.add_argument("--students-per-school", type=int, default=100, help="Students per school")
    parser.add_argument("--concurrency", type=int, default=50, help="Max concurrent requests")
    parser.add_argument("--output", default="performance-report.md", help="Output report file")
    args = parser.parse_args()

    cfg = SimConfig(
        base_url=args.base_url,
        num_schools=args.schools,
        students_per_school=args.students_per_school,
        concurrency=args.concurrency,
    )

    metrics = await run_simulation(cfg)
    report = generate_report(cfg, metrics)

    # Print summary to console
    s = metrics.summary()
    print(f"\n{'─'*50}")
    print(f"  Completed {s['total_requests']} requests in {s['duration_sec']}s")
    print(f"  Throughput: {s['throughput_rps']} req/s")
    print(f"  Latency p50={s['latency_p50_ms']}ms  p95={s['latency_p95_ms']}ms  p99={s['latency_p99_ms']}ms")
    print(f"  Errors: {s['error_count']} ({s['error_rate_pct']}%)")
    print(f"  Idempotency: {s['idempotency_hits']}/{cfg.idempotency_replays} de-duplicated")
    print(f"{'─'*50}\n")

    # Write report
    with open(args.output, "w") as f:
        f.write(report)
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
