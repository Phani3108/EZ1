# ADR 016 — Observability stack (Phase 6)

**Status**: Accepted (scaffolded 2026-05-26; per-service /metrics + tracing wired in code, OTLP backends + Loki + Alertmanager in a compose overlay)
**Closes (scaffolding)**: INFRA-007 (per-service /metrics), INFRA-008 (distributed tracing), INFRA-009 (centralized logs), PH6-1 (alertmanager rules)
**Closes (gate-tested on staging)**: pending — see `docs/runbooks/phase-6-observability-rollout.md`

## Context

EduZim has structured JSON logs from `eduzim_shared.logging` (since
Phase 0), a single `/metrics` on the api-gateway (INFRA-007 scaffold),
and a Sentry hook in `app_factory.create_app()` (INFRA-010 scaffold).
What's missing for production debuggability:

1. **Per-service metrics.** Today only the gateway exposes Prometheus
   metrics. The four downstream services + reporting consumer are
   invisible to Prometheus. Without per-service signals we can't
   correlate gateway 5xx to a specific service's degradation.
2. **Distributed tracing.** A parent's bad-attendance read crosses
   gateway → academics → potentially finance (dropout invoices). Today
   that whole flow lives in disconnected log lines correlated only by
   `request_id` — usable but slow. OpenTelemetry / Tempo turns it into
   a flame graph.
3. **Log aggregation.** Logs live in each container's stdout. Debugging
   means `docker logs <service>` per service. Loki + Promtail ship them
   into one queryable store with labels.
4. **Alerting.** Prometheus rules + Alertmanager routing. Without
   this, the operator has to remember to look at the dashboards.

## Decision

Wire all four signals as scaffolding in this repo; defer the
multi-region / cloud-hosted alternatives to Phase 7+.

### Metrics

* `eduzim_shared.metrics.install(app, service_name=...)` — installs a
  middleware + `/metrics` endpoint on any FastAPI app. Uses
  `prometheus-client` directly (over `prometheus-fastapi-instrumentator`)
  because we want explicit middleware, fewer deps, and tight
  cardinality control.
* Cardinality: `route` label is the URL **template** (`/students/{id}`),
  not the raw path. Unmatched paths bucket under `unmatched`.
* Auto-wired in `app_factory.create_app()` — every service gets
  `/metrics` for free; no per-service code changes needed.
* The gateway keeps its bespoke `gateway_*` collector for the
  edge-specific signals (rate-limit blocks, downstream errors per
  service). Both coexist on the gateway's `/metrics`.

### Tracing

* OpenTelemetry → OTLP/gRPC → Tempo.
* `eduzim_shared.tracing.install(service_name, app, sqlalchemy_engine)`
  — opt-in via `EDUZIM_TRACING_ENABLED=true`. No-op when disabled
  (no imports, no overhead).
* Auto-instruments FastAPI (every route), HTTPX (academics → finance
  dropout call, reporting service publish acks), SQLAlchemy (DB
  queries). Logging instrumentation adds `trace_id` / `span_id` to
  every JSON log record.
* W3C Trace Context propagation across the gateway boundary (FastAPI
  instrumentor reads `traceparent` from incoming requests, HTTPX
  instrumentor injects it into outgoing).
* Default sampler: `parentbased_traceidratio` at 10% — every trace
  the gateway samples is fully captured downstream; unsampled traces
  cost nothing.

### Logs

* Loki monolithic mode (single binary, single replica). For prod-
  scale log volume, migrate to read/write split or Grafana Cloud Loki.
* Promtail scrapes Docker container stdout via the host's docker
  socket. Compose service names become Loki labels (`service=academics`).
* `eduzim_shared.logging.JSONFormatter` already emits structured JSON;
  Promtail's `json` pipeline stage parses it and promotes `level`,
  `logger`, `request_id`, `trace_id` to Loki labels.
* Retention: 7 days dev, 30 days staging, longer in prod via S3
  backing.

### Alerts

* Four rules from the Phase 6 gate plus two "infrastructure baseline"
  rules:
  - Gateway 5xx > 1% (5m)        → critical
  - Kafka consumer lag > 30s     → critical
  - PgBouncer pool > 80% (5m)    → warning
  - Disk > 75% (10m)             → warning; > 90% (5m) → critical
  - Per-service 5xx > 5% (5m)    → warning
  - Any Prometheus target DOWN (2m) → critical
* Alertmanager routes:
  - `severity=critical` → Slack #ops-pages + email
  - `severity=warning`  → Slack #ops-digest (no page)
* Inhibition: when a critical fires, the corresponding warning is
  suppressed.

## Alternatives considered

* **Jaeger native exporter (over OTLP).** OTLP is the canonical
  protocol now; Tempo accepts it directly and Jaeger has OTLP
  bridges. No reason to pick the legacy path.
* **ELK (Elasticsearch + Kibana) for logs.** ~10× the operational
  footprint of Loki for marginal benefit at our log volume. Loki's
  label-based indexing is sufficient for the queries we run.
* **Datadog / New Relic / Honeycomb (hosted SaaS).** Cost-prohibitive
  at the parent-school price point we're targeting. Defer to a Phase
  7+ migration decision if budget changes.
* **Grafana Cloud (hosted Prometheus + Loki + Tempo).** Reasonable
  upgrade path; same query interface as self-hosted. Pricing model
  works once we're confident about volume — but until then,
  self-hosted is free.

## Consequences

* Every service now incurs ~1ms per request for the metrics
  middleware (timing + counter increment). Measured negligible
  against the request-handling itself.
* `prometheus-client` is now a hard dependency of `eduzim-shared`. The
  metrics middleware unconditionally installs.
* OpenTelemetry deps are optional (`eduzim-shared[tracing]`). Services
  that want tracing install the extra; the others get the no-op path.
* Sentry already wired in `app_factory` (INFRA-010 scaffold). Phase 6
  flips the live env (`SENTRY_DSN`) on per deploy.
* The observability stack adds **6 containers** (Loki, Promtail,
  Tempo, Alertmanager, postgres-exporter, pgbouncer-exporter, kafka-
  exporter, node-exporter — yes, 8 — Prometheus + Grafana already exist).
  ~1.5GB additional RAM. Budget node sizing accordingly.
* `/metrics` is **unauthenticated** on every service. The gateway's
  `/metrics` is on the same port as the public API but the path is
  not in the route table — so requests fall through to the 404
  handler. Downstream services' `/metrics` are similarly bound to
  port 8000 but only reachable from inside the docker network (no
  external port mapping). Lock down at the reverse-proxy layer in
  production.
* Loki / Tempo / Alertmanager use auth_enabled=false / no auth.
  Grafana fronts them — locking down Grafana with `GRAFANA_ADMIN_PASSWORD`
  is the access boundary. In prod, put Grafana behind an SSO proxy.

## Migration notes

* Production deploy: ensure each service's image has the
  `prometheus-client` and (optionally) `opentelemetry-*` packages.
  The `shared/setup.py` install_requires already pulls
  prometheus-client; tracing is opt-in via extras.
* Set `EDUZIM_TRACING_ENABLED=true` in production env.
* Set `SENTRY_DSN` per service (single project recommended; service
  name is on every event).
* Grafana admin password must be strong (default `admin/admin` is
  blocked by `GRAFANA_ADMIN_PASSWORD:?...` in the prod overlay).
* Alertmanager Slack webhooks: configure ALERT_SLACK_WEBHOOK_OPS_PAGES
  + ALERT_SLACK_WEBHOOK_OPS_DIGEST in `.env`. Without them, alerts
  fire but go to dead-letter Slack URLs.
