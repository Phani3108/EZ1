#!/usr/bin/env python3
"""
Realistic seed for Phase 7 load tests (Q-014 / INFRA-015).

Replaces the audit-flagged `scripts/scale_test.py` (550 mock HTTP
requests against localhost — not a real test). This script provisions
the full data-plane via the gateway API: a Ministry admin user, a
super-admin token, then N schools each with M students × T teachers ×
C classes × S subjects.

The output is `seed_artifacts.json` — the lookup table the load-test
script needs (user_ids, school_ids, class_ids, etc.).

Default sizing matches the Phase-7 gate (500 schools × 100 students ×
5 teachers). `--smoke` reduces to 10 schools × 20 students × 2
teachers for local dev / CI smoke runs.

Performance budget: the full 500-school seed should complete in
≤ 30 minutes on a 4-core / 8GB staging VPS. Watch the output —
the per-school timing prints lets the operator catch a degradation
mid-run.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("install httpx:  pip install httpx>=0.27.0", file=sys.stderr)
    sys.exit(1)


# ─── Sizing presets ───────────────────────────────────────────────


@dataclass
class Sizing:
    schools: int = 500
    students_per_school: int = 100
    teachers_per_school: int = 5
    classes_per_school: int = 5
    subjects_per_school: int = 6
    parents_per_student: int = 1     # 1 parent per student for v1; bump to 2 later
    concurrency: int = 50


SMOKE = Sizing(
    schools=10,
    students_per_school=20,
    teachers_per_school=2,
    classes_per_school=2,
    subjects_per_school=3,
    parents_per_student=1,
    concurrency=10,
)


# ─── Output schema ─────────────────────────────────────────────────


@dataclass
class SeedArtifacts:
    """The per-tenant lookup the load script reads.

    Schema (JSON):
    {
      "base_url": "...",
      "seeded_at": "...",
      "sizing": {...},
      "schools": [
         {
           "school_id": "<uuid>",
           "admin_user_id": "<uuid>",
           "admin_token": "<jwt>",
           "academic_year_id": "<uuid>",
           "term_id": "<uuid>",
           "classes": [{"id": "<uuid>", "name": "Grade 6 A"}],
           "subjects": [{"id": "<uuid>", "code": "MATH"}],
           "teachers": [{"user_id": "<uuid>", "token": "<jwt>"}],
           "students": [{"id": "<uuid>", "code": "STU001"}],
           "parents": [{"user_id": "<uuid>", "token": "<jwt>", "student_ids": [...]}]
         },
         ...
      ]
    }
    """
    base_url: str
    sizing: dict
    schools: list[dict] = field(default_factory=list)


# ─── Gateway API client ────────────────────────────────────────────


class GatewayClient:
    """Thin wrapper around httpx.AsyncClient with per-call timing."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    async def aclose(self):
        await self._client.aclose()

    async def post(self, path: str, *, json_body: dict, token: Optional[str] = None) -> httpx.Response:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await self._client.post(path, json=json_body, headers=headers)

    async def get(self, path: str, *, token: Optional[str] = None,
                  params: Optional[dict] = None) -> httpx.Response:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return await self._client.get(path, headers=headers, params=params)


# ─── Per-school seeding ────────────────────────────────────────────


async def seed_one_school(
    client: GatewayClient,
    school_idx: int,
    sizing: Sizing,
    super_admin_token: str,
) -> dict:
    """Provision ONE school + everyone in it. Returns the artifacts dict.

    All operations are await'd serially WITHIN a school because:
      (a) Foreign keys: students need a class to enrol in, marks need
          an assessment, etc.
      (b) Per-school work is the natural concurrency boundary; the
          outer loop fans out across schools.
    """
    school_label = f"sch-{school_idx:04d}"

    # ─ 1. Create school admin user via identity service ─
    admin_email = f"admin+{school_label}@loadtest.eduzim.invalid"
    admin_pw = f"AdminPw-{school_label}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/v1/auth/register", json_body={
        "email": admin_email,
        "password": admin_pw,
        "first_name": "Admin",
        "last_name": school_label.upper(),
        "role": "Admin",
    })
    r.raise_for_status()
    admin_user_id = r.json()["data"]["user_id"]

    # ─ 2. Log in to get the admin's access token ─
    r = await client.post("/api/v1/auth/login", json_body={
        "email": admin_email,
        "password": admin_pw,
    })
    r.raise_for_status()
    admin_token = r.json()["data"]["access_token"]

    # ─ 3. Create school ─
    r = await client.post("/api/v1/schools", token=admin_token, json_body={
        "name": f"Load Test School {school_idx:04d}",
        "country": "ZW",
        "timezone": "Africa/Harare",
    })
    r.raise_for_status()
    school_id = r.json()["data"]["id"]

    # ─ 4. Academic year + term ─
    r = await client.post("/api/v1/academics/years", token=admin_token, json_body={
        "name": "2026",
        "start_date": "2026-01-15",
        "end_date": "2026-12-15",
        "is_active": True,
    })
    r.raise_for_status()
    year_id = r.json()["data"]["id"]

    r = await client.post("/api/v1/academics/terms", token=admin_token, json_body={
        "academic_year_id": year_id,
        "name": "Term 1",
        "start_date": "2026-01-15",
        "end_date": "2026-04-15",
        "is_active": True,
    })
    r.raise_for_status()
    term_id = r.json()["data"]["id"]

    # ─ 5. Classes ─
    grades = [6, 7, 8, 9, 10][:sizing.classes_per_school]
    classes: list[dict] = []
    for grade in grades:
        r = await client.post("/api/v1/classes", token=admin_token, json_body={
            "name": f"Grade {grade}",
            "section": "A",
        })
        r.raise_for_status()
        cls = r.json()["data"]
        classes.append({"id": cls["id"], "name": cls["name"]})

    # ─ 6. Subjects ─
    subject_codes = ["MATH", "ENG", "SCI", "GEO", "HIST", "ART"][:sizing.subjects_per_school]
    subjects: list[dict] = []
    for code in subject_codes:
        r = await client.post("/api/v1/subjects", token=admin_token, json_body={
            "name": code.title(),
            "code": code,
        })
        r.raise_for_status()
        subj = r.json()["data"]
        subjects.append({"id": subj["id"], "code": subj["code"]})

    # ─ 7. Teachers (each gets a login + class assignment) ─
    teachers: list[dict] = []
    for t_idx in range(sizing.teachers_per_school):
        t_email = f"teacher+{school_label}-{t_idx}@loadtest.eduzim.invalid"
        t_pw = f"TeachPw-{school_label}-{t_idx}-{uuid.uuid4().hex[:8]}"
        r = await client.post("/api/v1/auth/register", json_body={
            "email": t_email,
            "password": t_pw,
            "first_name": f"Teacher{t_idx}",
            "last_name": school_label.upper(),
            "role": "Teacher",
        })
        r.raise_for_status()
        t_user_id = r.json()["data"]["user_id"]

        r = await client.post("/api/v1/auth/login", json_body={
            "email": t_email, "password": t_pw,
        })
        r.raise_for_status()
        t_token = r.json()["data"]["access_token"]

        # Assign teacher to a class (round-robin across classes).
        assigned_class = classes[t_idx % len(classes)]
        await client.post("/api/v1/class-teachers", token=admin_token, json_body={
            "teacher_user_id": t_user_id,
            "class_id": assigned_class["id"],
        })

        teachers.append({
            "user_id": t_user_id,
            "token": t_token,
            "class_id": assigned_class["id"],
        })

    # ─ 8. Students + per-class enrolment ─
    students: list[dict] = []
    for s_idx in range(sizing.students_per_school):
        student_code = f"{school_label.upper()}-S{s_idx:03d}"
        r = await client.post("/api/v1/students", token=admin_token, json_body={
            "student_code": student_code,
            "first_name": f"Student{s_idx}",
            "last_name": school_label.upper(),
            "dob": "2012-05-15",
            "gender": random.choice(["MALE", "FEMALE"]),
        })
        r.raise_for_status()
        student_id = r.json()["data"]["id"]

        # Enrol — round-robin across classes
        target_class = classes[s_idx % len(classes)]
        await client.post("/api/v1/enrollments", token=admin_token, json_body={
            "student_id": student_id,
            "class_id": target_class["id"],
            "academic_year_id": year_id,
        })
        students.append({"id": student_id, "code": student_code,
                         "class_id": target_class["id"]})

    # ─ 9. Parents (1 per student in v1; with a login each) ─
    parents: list[dict] = []
    for p_idx, student in enumerate(students[: sizing.students_per_school * sizing.parents_per_student]):
        p_email = f"parent+{school_label}-{p_idx}@loadtest.eduzim.invalid"
        p_pw = f"ParentPw-{school_label}-{p_idx}-{uuid.uuid4().hex[:8]}"
        r = await client.post("/api/v1/auth/register", json_body={
            "email": p_email,
            "password": p_pw,
            "first_name": f"Parent{p_idx}",
            "last_name": school_label.upper(),
            "role": "Parent",
        })
        r.raise_for_status()
        p_user_id = r.json()["data"]["user_id"]

        # Create the parent profile + link to user
        r = await client.post("/api/v1/parents", token=admin_token, json_body={
            "first_name": f"Parent{p_idx}",
            "last_name": school_label.upper(),
            "phone": f"+263{77_0000_0000 + school_idx * 1000 + p_idx}",
            "user_id": p_user_id,
            "relationship_type": "MOTHER",
        })
        if r.status_code in (200, 201):
            parent_id = r.json()["data"]["id"]
            # Link to student
            await client.post(
                f"/api/v1/students/{student['id']}/parents/{parent_id}",
                token=admin_token,
                json_body={"is_primary": True},
            )

        # Get parent's own token for use during load
        r = await client.post("/api/v1/auth/login", json_body={
            "email": p_email, "password": p_pw,
        })
        if r.status_code == 200:
            parents.append({
                "user_id": p_user_id,
                "token": r.json()["data"]["access_token"],
                "student_ids": [student["id"]],
            })

    return {
        "school_id": school_id,
        "admin_user_id": admin_user_id,
        "admin_token": admin_token,
        "academic_year_id": year_id,
        "term_id": term_id,
        "classes": classes,
        "subjects": subjects,
        "teachers": teachers,
        "students": students,
        "parents": parents,
    }


# ─── Orchestration ────────────────────────────────────────────────


async def seed_all(
    base_url: str,
    sizing: Sizing,
    super_admin_token: str,
    out_path: Path,
    log: logging.Logger,
) -> None:
    client = GatewayClient(base_url)
    artifacts = SeedArtifacts(
        base_url=base_url,
        sizing=sizing.__dict__,
    )

    semaphore = asyncio.Semaphore(sizing.concurrency)
    completed = 0
    failed = 0
    start_time = time.time()

    async def _one(school_idx: int):
        nonlocal completed, failed
        async with semaphore:
            try:
                t0 = time.time()
                result = await seed_one_school(client, school_idx, sizing, super_admin_token)
                completed += 1
                elapsed = time.time() - t0
                if completed % max(1, sizing.schools // 20) == 0 or completed == sizing.schools:
                    log.info(
                        "[seed] %d/%d schools done (last took %.1fs)",
                        completed, sizing.schools, elapsed,
                    )
                return result
            except httpx.HTTPStatusError as exc:
                failed += 1
                log.warning("[seed] school %d failed (%s): %s",
                            school_idx, exc.response.status_code,
                            exc.response.text[:200])
                return None
            except Exception as exc:  # noqa: BLE001
                failed += 1
                log.warning("[seed] school %d failed: %s", school_idx, exc)
                return None

    try:
        tasks = [_one(i) for i in range(sizing.schools)]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        artifacts.schools = [r for r in results if r is not None]
    finally:
        await client.aclose()

    elapsed_total = time.time() - start_time

    out_path.write_text(json.dumps({
        "base_url": artifacts.base_url,
        "sizing": artifacts.sizing,
        "seeded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "elapsed_seconds": round(elapsed_total, 1),
        "schools": artifacts.schools,
        "stats": {
            "requested": sizing.schools,
            "completed": completed,
            "failed": failed,
            "schools_per_second": round(completed / max(1, elapsed_total), 2),
        },
    }, indent=2))

    log.info(
        "[seed] DONE — %d/%d schools in %.1fs (%.1f schools/s). Output: %s",
        completed, sizing.schools, elapsed_total,
        completed / max(1, elapsed_total),
        out_path,
    )
    if failed:
        log.warning("[seed] %d schools FAILED; review log + retry as needed", failed)


# ─── CLI ──────────────────────────────────────────────────────────


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Realistic Phase-7 seed (replaces scripts/scale_test.py)",
    )
    parser.add_argument("--base-url", required=True,
                        help="Gateway base URL (e.g. http://localhost:8000)")
    parser.add_argument("--out", default="scripts/load/seed_artifacts.json")
    parser.add_argument("--super-admin-token",
                        default=os.environ.get("EDUZIM_SUPER_ADMIN_TOKEN", ""),
                        help="Optional super-admin JWT for routes that require it")
    parser.add_argument("--smoke", action="store_true",
                        help="Use small-scale sizing (10 schools × 20 students)")
    parser.add_argument("--schools", type=int)
    parser.add_argument("--students-per-school", type=int)
    parser.add_argument("--teachers-per-school", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("seed")

    sizing = SMOKE if args.smoke else Sizing()
    if args.schools is not None:
        sizing.schools = args.schools
    if args.students_per_school is not None:
        sizing.students_per_school = args.students_per_school
    if args.teachers_per_school is not None:
        sizing.teachers_per_school = args.teachers_per_school
    if args.concurrency is not None:
        sizing.concurrency = args.concurrency

    log.info("[seed] mode=%s schools=%d students/school=%d teachers/school=%d conc=%d",
             "smoke" if args.smoke else "full",
             sizing.schools, sizing.students_per_school,
             sizing.teachers_per_school, sizing.concurrency)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(seed_all(
        base_url=args.base_url.rstrip("/"),
        sizing=sizing,
        super_admin_token=args.super_admin_token,
        out_path=out_path,
        log=log,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
