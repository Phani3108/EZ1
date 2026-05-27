# EduZim load-test harness (Phase 7)

Replaces the audit-flagged `scripts/scale_test.py` (which was 550 mock
HTTP calls against localhost — not a real test).

Three deliverables here:

| Script | Purpose | Phase 7 task |
|---|---|---|
| `seed_realistic.py` | Provisions 500 schools × 100 students × 5 teachers via the gateway API. Real DB state, real tokens. | Q-014 / INFRA-015 |
| `load_24h.py` | Sustained 24-hour traffic with realistic school-day patterns. CSV time-series + JSON summary output. | PH7-1 |
| `report_generator.py` | Reads the JSON summary; writes `performance-report.md`. | PH7-4 |

The chaos profile (PH7-2) lives in `docker-compose.chaos.yml` at repo
root — a toxiproxy overlay that injects 5% packet loss + 200ms latency
+ periodic broker restart on the data-plane links.

## Quickstart

```bash
# 1. Boot the staging stack with HA + observability + chaos overlays
docker compose -f docker-compose.prod.yml \
               -f docker-compose.ha.yml \
               -f docker-compose.observability.yml \
               -f docker-compose.chaos.yml up -d
sleep 90   # let everything settle

# 2. Seed (~30 minutes on a typical staging VPS)
python scripts/load/seed_realistic.py \
    --base-url http://localhost:8000 \
    --schools 500 \
    --students-per-school 100 \
    --concurrency 50 \
    --out scripts/load/seed_artifacts.json

# 3. Run the 24-hour load test
python scripts/load/load_24h.py \
    --base-url http://localhost:8000 \
    --seed-artifacts scripts/load/seed_artifacts.json \
    --duration-hours 24 \
    --concurrency 200 \
    --out-csv scripts/load/load_24h.csv \
    --out-json scripts/load/load_24h_summary.json

# 4. Generate the report
python scripts/load/report_generator.py \
    --summary scripts/load/load_24h_summary.json \
    --csv scripts/load/load_24h.csv \
    --out docs/performance-report.md
```

## Smoke-mode

For local dev / CI, pass `--smoke` to each script. Reduces scale by ~50×
and runs for 5 minutes instead of 24 hours — useful for verifying the
harness itself before committing a full overnight run.

```bash
python scripts/load/seed_realistic.py --base-url http://localhost:8000 --smoke
python scripts/load/load_24h.py --base-url http://localhost:8000 \
    --seed-artifacts scripts/load/seed_artifacts.json --smoke
```

## What "realistic" means

The school-day pattern in `load_24h.py` models actual Zimbabwean
school traffic:

| Time (local) | Load profile |
|---|---|
| 06:00 – 07:30 | Ramp — parents check fees / yesterday's announcements |
| 07:30 – 13:00 | Burst — teachers mark attendance every period (8 periods/day), parent reads peak around lunch |
| 13:00 – 15:00 | Mid-burst — marks entry for morning assessments, more parent reads |
| 15:00 – 17:00 | Ramp-down — admin sees daily summary, fee payments trickle in |
| 17:00 – 22:00 | Evening — parent reads, fee payments, occasional admin work |
| 22:00 – 06:00 | Quiet — backend operations only (Kafka consumer keeps up) |

The script doesn't accelerate this 24-hour cycle into 24 minutes — it
runs at real time. The point of Phase 7 is to verify the system
behaves under sustained realistic load for a full day, not under
burst load for a few minutes.

## Outputs

- **`load_24h.csv`** — 1-minute time series. Columns: timestamp,
  endpoint, count, p50_ms, p95_ms, p99_ms, error_rate_pct.
- **`load_24h_summary.json`** — overall stats per endpoint. p50 / p95
  / p99 across the run, total requests, total errors, peak RPS, etc.
- **`docs/performance-report.md`** — human-readable summary with the
  numbers above + observations from the Grafana dashboards (operator
  pastes in screenshots).
