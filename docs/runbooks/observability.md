# Observability Runbook

> **Scope**: what Prometheus / Grafana / Sentry scaffold ship today, how to use them, what's deliberately deferred.
> **Related**: INFRA-007, INFRA-010 (Phase 6); ADR 005, ADR 007.
> **Status**: dev scaffold live 2026-05-26. Production wiring (Loki logs, OTel tracing, Alertmanager rules) is Phase 17 work.

---

## What ships today

| Component | Purpose | URL (dev) |
|---|---|---|
| `prometheus` container | Scrapes `/metrics` on a 15s interval; retains 15 days of TSDB data on a named volume | `http://localhost:9090` |
| `grafana` container | Pre-provisioned with the Prometheus datasource and one starter dashboard ("Gateway Overview") | `http://localhost:3030` (admin/admin) |
| `pg-backup` container | Daily `pg_dump` + 14-snapshot retention (see `backup-restore.md`) | — |
| Sentry SDK hook in shared `app_factory` | Initialized only when `SENTRY_DSN` is set in env; honours `traces_sample_rate`, `environment`, `release` tags | — |

The dashboard surfaces: gateway request rate, 5xx %, rate-limit blocks/sec,
downstream error rate, per-route request rate, per-route p95 latency.

## How to use it locally

```bash
docker compose up -d prometheus grafana
# Browse:
#   http://localhost:9090            (Prometheus UI; targets must be UP)
#   http://localhost:3030            (Grafana; admin/admin)
```

The Gateway Overview dashboard auto-loads at first launch.

## Wiring Sentry (production)

1. Create a Sentry project for each EduZim service (or one project with
   release tags — both work).
2. Store the DSN in your secrets manager. Inject it as `SENTRY_DSN` env
   var on each service container.
3. Optional: `SENTRY_TRACES_SAMPLE_RATE` (default 0.0 = no perf data),
   `SENTRY_ENVIRONMENT` (default "dev").
4. PII protection: `send_default_pii=False` is hard-coded in
   `shared/eduzim_shared/app_factory.py` per ADR 007. Do **not** flip
   this without a privacy review.

The factory hook is a no-op if `sentry-sdk` isn't installed. To enable:

```bash
pip install sentry-sdk[fastapi]
```

Add `sentry-sdk[fastapi]>=2.0.0` to each service's `requirements.txt`
when you're ready to ship Sentry to production.

## What `/metrics` is currently scraped

- `api-gateway:8000/metrics` — uses the in-house `MetricsCollector`
  emitting `gateway_requests_total`, `gateway_request_duration_ms_*`,
  `gateway_downstream_errors_total`, `gateway_rate_limit_blocks_total`.

## What's NOT scraped (deferred — `task.md` Phase 6 follow-up)

- Per-service `/metrics`. The follow-up adds
  `prometheus-fastapi-instrumentator` via `shared/app_factory` so every
  service exposes `/metrics` automatically. Once that's in, uncomment the
  matching `scrape_configs` blocks in `infra/observability/prometheus.yml`.

## What's also deferred (major-overhaul, Phase 5/17)

| Item | Why deferred |
|---|---|
| Distributed tracing (Jaeger / Tempo + OTel SDK in every service) | Substantial wiring effort; not blocking the persona-feature build |
| Centralised logs (Loki + Promtail) | Same — needs careful log-shape standardisation first |
| Alertmanager rules + paging | Needs an on-call rota first; meaningless without one |
| Real SLA dashboards (per-school SLO, regional p95) | Needs production traffic for a baseline |
| Multi-region scraping | ADR 005 says one region until Year 2 |

## Verifying the scrape pipeline (dev)

```bash
# 1. Stack up
docker compose up -d

# 2. Make some gateway traffic
curl -sS http://localhost:8000/health
# (or run a few login attempts to populate request_count + rate_limit_blocks)

# 3. Confirm Prometheus is scraping
open http://localhost:9090/targets   # api-gateway should show "UP"

# 4. Inspect the Grafana dashboard
open http://localhost:3030           # admin/admin → Dashboards → EduZim → Gateway Overview
```

If the gateway target shows `DOWN` in Prometheus, the gateway container
isn't running or `/metrics` is returning non-200. Check
`docker compose logs api-gateway`.
