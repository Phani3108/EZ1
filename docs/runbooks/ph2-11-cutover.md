# PH2-11 Cutover — Reporting HTTP → Academics + Pure Consumer

This runbook documents the staging→prod flip for PH2-11.

## What changes

| Surface | Before | After |
|---|---|---|
| `GET /api/v1/reports/dashboard` | reporting-service | **academics** (reads `reporting_db` read-only) |
| `GET /api/v1/reports/attendance/trend` | reporting-service | **academics** |
| `GET /api/v1/reports/financial/summary` | reporting-service | **academics** |
| `GET /api/v1/reports/dropout/*` | reporting-service (3 HTTP hops) | **academics** (in-process students+attendance; 1 HTTP hop to finance for invoices) |
| `GET /api/v1/reports/export/*` | reporting-service | **academics** |
| `POST /api/v1/reports/consume` | reporting-service HTTP | **CLI**: `python -m cli.consume_events <file>` |
| `POST /api/v1/reports/rebuild` | reporting-service HTTP | **CLI**: `python -m cli.rebuild_projections <file> --confirm` |
| reporting-service container | uvicorn FastAPI on :8000 | `python -m app.consumer` — no port exposed |

## Why

ADR 006 calls for reporting to become "an asynchronous projection consumer (still separate process; not a microservice for HTTP)". PH2-11 executes that: the read surface joins the academics service (one fewer downstream HTTP hop for every dashboard load); the write surface (HTTP `/reports/consume`) is replaced by a Kafka consumer loop that reads events directly from the topic stream.

## Pre-flight (staging)

1. Confirm `academics` container has `REPORTING_DATABASE_URL` set:
   ```bash
   docker compose -f docker-compose.prod.yml exec academics printenv REPORTING_DATABASE_URL
   ```
   Expected: `postgresql://eduzim:***@postgres:5432/reporting_db`.

2. Confirm reporting-service container CMD is the consumer:
   ```bash
   docker compose -f docker-compose.prod.yml exec reporting-service ps -ef | grep -v grep
   ```
   Expected: `python -m app.consumer` (NOT `uvicorn`).

3. Confirm reporting consumer has subscribed:
   ```bash
   docker compose -f docker-compose.prod.yml logs reporting-service | grep reporting.consumer.starting
   ```
   Expected one line: `reporting.consumer.starting topics=[…]`.

## Flip the gateway (staging)

Already wired in the SERVICE_ROUTES table — `/api/v1/reports` → `ACADEMICS_SERVICE_URL`. No runtime flag; the routing is in code. Deploy the gateway image built from this commit and the routes flip.

## Smoke test

```bash
TOKEN=$(curl -sX POST $GATEWAY/api/v1/auth/login -d '{"email":"admin@school","password":"…"}' | jq -r .access_token)

# Dashboard read (used to hit reporting-service:8007; now academics:8009)
curl -sX GET $GATEWAY/api/v1/reports/dashboard -H "Authorization: Bearer $TOKEN" | jq .data

# Dropout (used to be 3 HTTP hops; now 1)
curl -sX GET "$GATEWAY/api/v1/reports/dropout/summary" -H "Authorization: Bearer $TOKEN" | jq .data
```

Each should return data identical to the pre-cutover response. Latency on `/dropout/summary` should drop noticeably (~40–60% on staging-typical 100-student schools).

## Rollback

If a regression appears within the burn-in window:

1. Re-point the gateway's `/api/v1/reports` route back at reporting-service. Edit `services/api-gateway/app/routes.py`:
   ```python
   "/api/v1/reports": ("REPORTING_SERVICE_URL", "reporting-service"),
   ```
2. Restart the reporting-service container with the **previous** Dockerfile CMD (`uvicorn app.main:app --host 0.0.0.0 --port 8000`) so the HTTP routes come back online. The route files in `app/api/routes.py` and `app/api/exports.py` are still on disk (they emit a DeprecationWarning on import but otherwise work).
3. Restart the gateway.

The projection DB layout has not changed, so no data migration is needed for rollback.

## After 1 week of clean burn-in

* Move on to PH2-12: delete the four retired per-service folders (school/student/attendance/assessment), and delete `services/reporting-service/app/api/` (the dead HTTP routes). The reporting consumer + CLI tooling stay.
