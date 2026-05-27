# ADR 017 — Real load-testing strategy (Phase 7)

**Status**: Accepted (scaffolded 2026-05-26; awaiting 24-hour staging run)
**Closes (scaffolding)**: Q-014 / INFRA-015, PH7-1, PH7-2, PH7-4
**Closes (gate)**: pending — 24-hour run on staging with reasonable verdicts

## Context

Phase-1 audit (`task.md §4`) caught `scripts/scale_test.py` red-handed:
the existing "500-school validated" claim came from a script that
fired ~550 mock HTTP requests against `localhost` and called the
result a scale test. The audit's exact words: "550 mock HTTP requests
against localhost. Not a scale test."

This ADR locks in what a defensible load test actually is for EduZim
and what we'll publish in the performance-report from now on.

## Decision

A defensible Phase-7 load test has four properties:

1. **Real DB state.** No mocks. The seed script provisions actual
   schools / users / classes / students / parents through the gateway
   API. The DB rows exist; the JWTs are real and were issued by the
   identity service.

2. **Sustained at realistic scale.** 500 schools × 100 students × 5
   teachers — the Phase-1 gate target. Smoke mode at ~50× smaller for
   CI / dev verification.

3. **Sustained over a real day, not a real minute.** The 24-hour run
   exercises the system under the actual school-day pattern (peak
   teacher activity 08:00–13:00, parent peak 17:00–22:00, quiet
   overnight). Compressed runs miss garbage-collection cliffs, Kafka
   retention boundaries, log-rotation pressure, and connection-pool
   long-tail behaviour.

4. **With chaos enabled.** toxiproxy injects 5% packet loss and 200ms
   latency on data-plane connections. The system's published SLOs
   apply UNDER this profile, not on a perfect network.

The deliverables that meet those properties:

- **`scripts/load/seed_realistic.py`** — provisions everything via
  the gateway API. Output: `seed_artifacts.json` (the lookup the load
  script needs — user_ids, tokens, school_ids, class_ids).
- **`scripts/load/load_24h.py`** — drives sustained traffic with the
  school-day profile. Output: 1-minute time series CSV + per-endpoint
  summary JSON.
- **`scripts/load/report_generator.py`** — renders
  `docs/performance-report.md` from the run output, with explicit
  pass/fail per endpoint against published p99 budgets.
- **`scripts/load/chaos_profiles.sh`** + **`docker-compose.chaos.yml`**
  — toxiproxy overlay that injects the chaos profile.
- **`scripts/scale_test.py`** marked DEPRECATED with a CLI-level
  abort message. Removal scheduled for PH8.

## p99 budgets

The report generator compares per-endpoint p99 latency against these
budgets (in `scripts/load/report_generator.py:P99_BUDGETS_MS`):

| Endpoint family | p99 budget | Why |
|---|---:|---|
| Teacher writes (attendance / marks / announcement) | 500 ms | Batch-acked; UI tolerates a small delay on the "saved" toast. |
| Parent reads (children / student / feed) | 300 ms | Mobile UX; anything over 300ms feels laggy. |
| Parent attendance trend | 400 ms | Slightly heavier query; still mobile-budget. |
| Parent fees | 400 ms | Same. |
| Admin dashboard | 800 ms | Projection-DB read; heavier query. |
| Admin attendance trend | 600 ms | Time-range scan. |
| Admin dropout summary | 1500 ms | In-process gather across multiple tables + 1 HTTP hop to finance. Highest budget. |

All endpoints share a **0.5% error-rate gate** — any endpoint with
> 0.5% 5xx fails the report.

These budgets are intentionally CONSERVATIVE for the African ISP
backbone target. Production should beat them on a clean network and
meet them under chaos.

## Alternatives considered

* **k6 / Locust / JMeter / Gatling.** Industry-standard load
  generators, all of which we considered. Reasons we wrote our own
  thin script instead:
  - Per-endpoint sequencing (a teacher posting attendance must use
    THEIR token, against THEIR class's students) is awkward in k6's
    JavaScript-DSL and in Locust's user-group abstraction. The seed
    artifacts JSON + bespoke Python loop is simpler to reason about.
  - Realistic school-day patterns mean varying RPS by hour-of-day,
    not a flat target. k6 supports this via stages but it's clunky.
  - We don't want a new tool in the operator's runbook. Python +
    httpx is already in everyone's toolbox.
  - The test harness should be readable code we maintain, not a YAML
    config someone wrote 3 years ago.
* **Hosted load testing (Loader.io, BlazeMeter, k6 Cloud).** Would
  remove the "spin up a beefy box" problem, but the test traffic
  origins from outside the data-residency boundary (Debate 5 still
  open). Self-hosted load gen runs from inside the same AWS region
  (or Zimbabwean cloud) as the SUT.
* **Real shadow traffic** (mirror prod traffic into staging at
  k-rate). Best signal once we have prod traffic. Phase 14+, post-pilot.

## Consequences

* `scripts/scale_test.py` is now a no-op with a deprecation banner.
  Any operational tooling that pointed at it will see the banner +
  exit 2 — easy to spot in CI logs.
* `docs/performance-report.md` will be generated fresh per run. The
  previous marketing version will be overwritten. We keep one copy
  per dated run in `docs/perf-reports/YYYY-MM-DD.md` so history is
  auditable.
* The 24-hour run uses the full HA + observability + chaos stack
  (`-f docker-compose.prod.yml -f docker-compose.ha.yml -f
  docker-compose.observability.yml -f docker-compose.chaos.yml`).
  Staging node needs ~8 vCPU + 16 GB RAM to run all 14+ containers.
* Operator effort: ~30 minutes to seed, 24 hours to load, ~10
  minutes to generate the report. Plan for two days of staging
  occupancy per run.
* The seed runs through the GATEWAY (not direct service hits), so
  it exercises auth, RBAC, the JWT pipeline, AND tests that the
  full provisioning flow works end-to-end. The first 50 schools
  worth of seeding is itself a smoke test for the deploy.

## Migration notes

* Replace any existing `scripts/scale_test.py` invocation with the
  new three-script flow. See `scripts/load/README.md` for commands.
* CI: add `python -m pytest scripts/load/test_report_generator.py`
  to the existing pytest matrix. The other two load scripts can't
  run in CI (no live gateway), but a syntax-check + `--help` parse
  is reasonable smoke.
* Performance-report storage: commit `docs/perf-reports/<date>.md`
  per run so the history is visible in git log.
