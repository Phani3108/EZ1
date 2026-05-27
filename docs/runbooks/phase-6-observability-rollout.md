# Phase 6 — Observability rollout runbook

This runbook covers the Phase 6 deliverables:

  1. **INFRA-007** — per-service `/metrics` (wired via `app_factory.create_app`).
  2. **INFRA-008** — distributed tracing via OpenTelemetry → Tempo.
  3. **INFRA-009** — log aggregation via Loki + Promtail.
  4. **INFRA-010** — error tracking via Sentry (env wiring done; DSN per deploy).
  5. **PH6-1** — Alertmanager rules + routing.

## Topology

```
                                   ┌───────────────────────┐
                                   │   Grafana (3030)      │
                                   │  (admin UI + alerts   │
                                   │   inbox)              │
                                   └───┬──────┬─────────┬──┘
                                       │      │         │
                              ┌────────┴──┐ ┌─┴──┐ ┌────┴───┐
                              │Prometheus │ │Loki│ │ Tempo  │
                              └─┬─────┬───┘ └─┬──┘ └────────┘
                                │     │       │           ▲
                          scrape│     │push   │           │OTLP
                                │     ▼       │push       │/4317
              ┌─────────────────┘  Alertmgr   │           │
              │                    (9093)     │           │
        every service              │          │           │
        /metrics                   ▼          │           │
              ▲                Slack/email    │           │
              │                                │           │
              │                                │           │
   ┌──────────┼──────────────┬─────────────────┼───────────┴───────┐
   │       gateway        academics        ... reporting           │
   │       finance        identity              consumer           │
   │       communications                                          │
   │       (each runs Promtail-tailed docker stdout)               │
   └────────────────────────────────────────────────────────────────┘
```

## Pre-deploy

1. **Pull the additional images.** The first run is ~600MB total
   across Loki/Tempo/Promtail/Alertmanager/exporters.

2. **Set new env vars** in `.env`:
   ```bash
   # Grafana admin (required by the prod overlay)
   GRAFANA_ADMIN_USER=admin
   GRAFANA_ADMIN_PASSWORD=<strong-pw>

   # Tracing — set to "true" to wire OpenTelemetry on every service
   EDUZIM_TRACING_ENABLED=true

   # Sentry — set the DSN to wire error tracking
   SENTRY_DSN=https://<your-dsn>@sentry.io/<project>
   SENTRY_ENVIRONMENT=staging
   SENTRY_TRACES_SAMPLE_RATE=0.05

   # Alertmanager routing — leave blank to disable channels
   ALERT_SMTP_HOST=smtp.example.com:587
   ALERT_SMTP_USER=alerts@eduzim.invalid
   ALERT_SMTP_PASSWORD=<smtp-pw>
   ALERT_EMAIL_FROM=alerts@eduzim.invalid
   ALERT_EMAIL_TO_ENG=eng@eduzim.invalid
   ALERT_SLACK_WEBHOOK_OPS_PAGES=https://hooks.slack.com/services/.../...
   ALERT_SLACK_WEBHOOK_OPS_DIGEST=https://hooks.slack.com/services/.../...
   ```

3. **Install the tracing extras** in each service image. Either:
   - Add `opentelemetry-*` to each service's `requirements.txt`, OR
   - Update each service Dockerfile's pip install line to add
     `eduzim-shared[tracing]`.

   The tracing module silently no-ops when the otel libs are absent
   (logs a warning) — so this step is optional if you're not running
   real tracing yet.

## First-time deploy

```bash
# Build (rebuilds service images with the new shared deps)
docker compose -f docker-compose.prod.yml \
               -f docker-compose.observability.yml build

# Bring up the observability backends first
docker compose -f docker-compose.prod.yml \
               -f docker-compose.observability.yml up -d \
               prometheus alertmanager loki promtail tempo \
               node-exporter postgres-exporter pgbouncer-exporter kafka-exporter \
               grafana

sleep 30   # let collectors settle

# Bring up the rest
docker compose -f docker-compose.prod.yml \
               -f docker-compose.observability.yml up -d
```

## Smoke tests

```bash
# /metrics on every service returns prometheus exposition format
for svc in api-gateway identity academics finance communications; do
    echo "=== $svc /metrics ==="
    docker compose -f docker-compose.prod.yml exec "$svc" \
        curl -fsS http://localhost:8000/metrics | head -10
done

# Prometheus is scraping every target
curl -fsS http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'

# Loki has logs from every service
curl -fsS "http://localhost:3100/loki/api/v1/labels" | jq .

# Tempo accepts an OTLP test span
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml \
    exec tempo wget -qO- http://localhost:3200/ready

# Alertmanager loaded the rules
curl -fsS http://localhost:9093/api/v2/status | jq '.config'

# Grafana datasources all green
curl -fsS -u "${GRAFANA_ADMIN_USER}:${GRAFANA_ADMIN_PASSWORD}" \
    http://localhost:3030/api/datasources | jq '.[].name'
# Expect: ["Prometheus", "Loki", "Tempo"]
```

## Verify the alert flow

The Phase 6 gate calls for: "Synthetic 500 error in gateway triggers
Sentry capture and Alertmanager page within 60s."

```bash
# 1. Force a gateway 5xx (Phase 7-1 test endpoint, or any malformed request
#    that bypasses validation).
for i in {1..100}; do
    curl -s -o /dev/null http://localhost:8000/api/v1/nonexistent
done

# 2. Wait 5m for the GatewayHighErrorRate rule to fire (5% threshold + 5m for clause).
sleep 360

# 3. Check Alertmanager
curl -fsS http://localhost:9093/api/v2/alerts | jq '.[] | {labels, status}'
# Expect: at least one entry with alertname=GatewayHighErrorRate, status.state=active

# 4. Check Sentry inbox (browser): SENTRY_DSN should have 5xx events
#    from api-gateway service.

# 5. Check Slack #ops-pages channel: should have a message
#    "🚨 GatewayHighErrorRate (api-gateway)"
```

## Rollback

The observability stack is purely additive. To remove:

```bash
docker compose -f docker-compose.prod.yml \
               -f docker-compose.observability.yml down \
               prometheus grafana alertmanager loki promtail tempo \
               node-exporter postgres-exporter pgbouncer-exporter kafka-exporter

# App services keep running with no observers.
```

To disable tracing without removing the stack, set
`EDUZIM_TRACING_ENABLED=false` in `.env` and restart app services —
the `tracing.install(...)` call becomes a no-op.

## Known caveats

- **/metrics is unauthenticated.** All service /metrics endpoints are
  reachable from inside the docker network with no auth. Don't expose
  them publicly. The gateway's port-8000 has the `/metrics` route
  defined; production reverse-proxy should strip the path before
  forwarding to the public internet.
- **OpenTelemetry packages add ~80MB to each service image.** Optional
  install — services that don't need tracing get the no-op path.
- **Tempo / Loki local-disk storage** is 7-day retention by default.
  Long-term retention requires S3 backing or migration to Grafana Cloud.
- **Alertmanager Slack webhooks** must be real URLs. Without them, the
  POST silently fails and alerts only land in email (or nowhere).
- **Grafana default credentials** are blocked by `GRAFANA_ADMIN_PASSWORD:?`
  in the prod overlay — first deploy will fail until you set it.
- **The Kafka exporter** binds to `kafka:9092` (single-broker). Under
  the HA overlay it should be `kafka-0:9092,kafka-1:9092,kafka-2:9092`
  — overlay this with the HA exporter env in a follow-up if needed.
