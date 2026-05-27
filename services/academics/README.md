# academics service (shell)

> **Status**: PH2-5 shell. Not wired to the gateway. No business logic yet.
>
> Future merges (PH2-6 → PH2-9) populate this service with the consolidated
> code from `school-service`, `student-service`, `attendance-service`, and
> `assessment-service` per ADR 006 and its addendum
> (`docs/decisions/006-addendum-module-call-graph.md`).

## Target shape (per addendum)

```
services/academics/
  app/
    main.py
    config.py
    database.py              # academics_db
    dependencies.py
    events.py                # all academics topics
    api/
      schools.py             # /schools, /schools/current
      academics.py           # /academic-years, /terms
      classes.py             # /classes, /subjects, /class-teachers, /teachers/me/classes
      students.py            # /students, /parents, /enrollments, /students/{id}/parents
      attendance.py          # /attendance (sync, records, daily, trend, class-summary)
      assessments.py         # /assessments, marks
      geo.py                 # /provinces, /districts
      bulk.py                # /students/import, /students/bulk-enroll, /students/promote
      reports_query.py       # GET /reports/* (reads reporting projection)
    models/
      school.py
      student.py
      attendance.py
      assessment.py
      idempotency.py
    schemas/
    services/
      school_service.py
      student_service.py
      attendance_service.py
      assessment_service.py
      authorization.py       # in-process replacement for /internal/teachers/authorize etc.
  alembic/                   # consolidated migrations
  tests/
```

## What's here today (shell only)

- `app/main.py` — FastAPI app with `/health` only.
- `app/config.py` — required env declarations.
- `app/services/authorization.py` — interface stubs for the intra-process
  authz functions that PH2-8 / PH2-9 will implement once the school + student
  schemas live here.
- `tests/test_shell.py` — proves the shell starts and `/health` returns 200.

The empty `api/`, `models/`, `schemas/`, `services/` directories are placeholders.
