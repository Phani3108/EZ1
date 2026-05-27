# Phase 7 — Real load test runbook

This runbook covers the **24-hour realistic load test** that closes
Phase 7's gate. Successful completion replaces the audit-flagged
`scripts/scale_test.py` (550 mock HTTP calls — see ADR 017) with a
real benchmark.

## Prereqs

- Phase 5 + Phase 6 chaos/observability gates passed (so the HA stack
  is verified and Prometheus/Loki/Tempo are scraping cleanly).
- A staging VPS with ≥ 8 vCPU + 16 GB RAM available for ~48 hours.
  ~24h load + ~24h slack for runbook execution + report generation.
- An EduZim Slack / email setup configured so Alertmanager pages
  during the run land somewhere (see Phase 6 runbook).
- ~50 GB free disk for log + metric retention during the run.

## Test plan

1. **Pre-run smoke (5 min):** verify the harness with `--smoke` mode
   so a real misconfiguration doesn't burn 24 hours.
2. **Seed (30 min):** provision 500 schools × 100 students × 5 teachers
   via the gateway API.
3. **24-hour load:** sustained school-day traffic with chaos enabled.
4. **Report:** generate `docs/performance-report.md` + commit to
   `docs/perf-reports/YYYY-MM-DD.md` for history.
5. **Post-mortem:** triage any p99-budget failures + error spikes.

## 1. Pre-run smoke

```bash
# Boot the full stack
docker compose \
    -f docker-compose.prod.yml \
    -f docker-compose.ha.yml \
    -f docker-compose.observability.yml \
    -f docker-compose.chaos.yml \
    up -d

# Apply the chaos profile
./scripts/load/chaos_profiles.sh apply

# Wait for the cluster to settle (especially repmgr + KRaft elections)
sleep 120

# Smoke-seed (10 schools, ~2 min)
python scripts/load/seed_realistic.py \
    --base-url http://localhost:8000 \
    --smoke \
    --out scripts/load/_smoke_seed.json

# Smoke-load (5 min compressed run)
python scripts/load/load_24h.py \
    --base-url http://localhost:8000 \
    --seed-artifacts scripts/load/_smoke_seed.json \
    --smoke \
    --out-csv scripts/load/_smoke_load.csv \
    --out-json scripts/load/_smoke_summary.json

# Smoke-report
python scripts/load/report_generator.py \
    --summary scripts/load/_smoke_summary.json \
    --csv scripts/load/_smoke_load.csv \
    --out scripts/load/_smoke_report.md

# Eyeball the smoke report
less scripts/load/_smoke_report.md
```

If the smoke verdict is ✅ PASSED, the harness is wired correctly and
you can commit to the 24-hour run. If it's ❌ FAILED on infrastructure
(any service down, gateway 5xx) — fix that before going further.

## 2. Real seed

```bash
# Reset chaos to baseline (proxies stay, toxics cleared) so seeding
# isn't penalised by the chaos profile
./scripts/load/chaos_profiles.sh reset

# Full seed — ~30 min
nohup python scripts/load/seed_realistic.py \
    --base-url http://localhost:8000 \
    --schools 500 \
    --students-per-school 100 \
    --teachers-per-school 5 \
    --concurrency 50 \
    --out scripts/load/seed_artifacts.json \
    > scripts/load/seed.log 2>&1 &

tail -f scripts/load/seed.log
```

Expected output: every ~25 schools, a `[seed] N/500 schools done`
line. The full 500 should land in 20–40 min. Any individual school
failure is non-fatal (it's logged + skipped); the final summary line
prints the count.

Sanity-check the seed:
```bash
jq '.stats' scripts/load/seed_artifacts.json
# Expect: {"requested": 500, "completed": 500, "failed": 0, "schools_per_second": ~0.3}
```

## 3. 24-hour load

```bash
# Re-apply chaos
./scripts/load/chaos_profiles.sh apply

# Start the 24-hour run. nohup so it survives SSH disconnects.
nohup python scripts/load/load_24h.py \
    --base-url http://localhost:8000 \
    --seed-artifacts scripts/load/seed_artifacts.json \
    --duration-hours 24 \
    --concurrency 200 \
    --out-csv scripts/load/load_24h.csv \
    --out-json scripts/load/load_24h_summary.json \
    > scripts/load/load_24h.log 2>&1 &

# Check it's alive
ps aux | grep load_24h
tail -f scripts/load/load_24h.log
```

While the run is in flight:
- Open Grafana (`http://localhost:3030`, login per Phase 6 runbook)
- Watch the "Services Overview" + "Gateway Overview" dashboards.
- If any of the Phase 6 alerts fires, screenshot the dashboard +
  note the timestamp; they'll go into the post-mortem.

## 4. Report

After 24 hours:

```bash
# Confirm the run completed
tail -5 scripts/load/load_24h.log
# Expect: [load] DONE. CSV: ...   JSON: ...

# Grafana screenshots — capture at least:
#   - Services Overview at peak hour (10:30 local)
#   - Gateway Overview for the whole run
#   - Tempo: a sample trace from a parent_attendance_trend call

# Save them as PNGs in docs/perf-reports/screenshots/
mkdir -p docs/perf-reports/screenshots/

# Generate the report
DATE=$(date -u +%F)
python scripts/load/report_generator.py \
    --summary scripts/load/load_24h_summary.json \
    --csv scripts/load/load_24h.csv \
    --include-grafana-screenshots "docs/perf-reports/screenshots/services-peak.png,docs/perf-reports/screenshots/gateway-overview.png,docs/perf-reports/screenshots/trace-sample.png" \
    --out "docs/perf-reports/${DATE}.md"

# Also overwrite the canonical performance-report.md so the latest
# always shows in the docs root.
cp "docs/perf-reports/${DATE}.md" docs/performance-report.md
```

Commit the report:
```bash
git add docs/perf-reports/ docs/performance-report.md
git commit -m "Phase 7 load test: ${DATE} run"
```

## 5. Post-mortem (for any ❌ FAILED endpoint)

For each endpoint that failed its p99 budget OR exceeded 0.5% errors:

1. Open the Grafana p99 panel for that endpoint at the time of
   failure. Was it a sustained slow period or a single spike?
2. Open Tempo. Filter `service = <degraded service> AND duration >
   <budget>` — view a representative slow trace. Where's the time
   going? (DB, downstream HTTP, app CPU?)
3. Open Loki for the same window. Filter `service = <s> AND level
   = error`. Is there a stack trace pattern?
4. Cross-reference with Alertmanager firings — did a Kafka broker
   restart (PH7-2 chaos) coincide?

Write the findings into the report (Observations section, next to
the screenshots).

## Rollback / cleanup

```bash
# Stop the load
pkill -f load_24h.py

# Remove chaos profile (return data-plane to normal)
./scripts/load/chaos_profiles.sh remove

# Tear down the stack
docker compose \
    -f docker-compose.prod.yml \
    -f docker-compose.ha.yml \
    -f docker-compose.observability.yml \
    -f docker-compose.chaos.yml \
    down

# Optionally also wipe volumes (will lose the seeded data — fine
# since seed_realistic.py is idempotent for the next run):
docker compose down -v
```

## Known caveats

- The seed creates ~3,000 user accounts (1 admin + 5 teachers + 100
  parents per school × 500 schools). Identity-service is a single
  node in HA mode — it CAN handle this but the seed deliberately
  caps concurrency at 50 so it doesn't saturate. On a fast staging
  box you can push `--concurrency 100`.
- The chaos profile applies 200ms latency + 5% timeout (long timeout
  threshold of 20s, so ≤5% of long connections drop). For a more
  aggressive profile, edit `scripts/load/chaos_profiles.sh`.
- The 24-hour script does not exercise `POST /api/v1/fees/payments`
  (real money flows). Phase 7 is read-and-write on the platform's
  internal state; the payment provider integration is a separate
  Phase 8+ flow.
- p99 in the JSON summary is "p99 of per-minute p99s" — an
  approximation. For exact run-wide p99, query Prometheus directly
  (the report's "Limitations" section shows the PromQL).
- If the run is aborted mid-flight, the CSV is still valid (it's
  flushed per-minute) and `report_generator.py` will work — it just
  shows a shorter duration in the summary.
