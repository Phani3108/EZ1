# Phase 5 — HA rollout runbook

This runbook covers the four Phase-5 deliverables:

  1. **INFRA-003** — Postgres HA (bitnami repmgr 2-node + pgpool routing).
  2. **INFRA-004 / INFRA-005** — Kafka 3-broker KRaft cluster + kafka-ui.
  3. **INFRA-006** — Redis Sentinel (1 primary + 1 replica + 3 sentinels).
  4. **INFRA-019** — Service-to-service mTLS.

All four land as the `docker-compose.ha.yml` overlay that composes with
`docker-compose.prod.yml`. Single-node prod (`docker-compose.prod.yml`
alone) still works for low-stakes deployments; HA mode is opt-in via
the overlay.

## Topology summary

Single-node (status quo):
```
client → gateway → service → pgbouncer → postgres
                              \________ kafka (1 broker, zookeeper)
                              \________ redis (1 node)
```

HA (Phase 5):
```
client → gateway → service → pgbouncer → pgpool → pg-0 (primary)
                                                 → pg-1 (standby; auto-promoted by repmgr)
                              \________ kafka-0 / kafka-1 / kafka-2 (KRaft quorum)
                              \________ redis-master / redis-replica  + sentinel-0/1/2
                              \________ all comms over mTLS (when EDUZIM_TLS_ENABLED=true)
```

## Pre-deploy

1. **Generate mTLS certs** (staging-only; prod uses cert-manager once
   we move to k8s):
   ```bash
   ./scripts/generate-mtls-certs.sh
   ls infra/certs/   # ca.crt + ca.key + <service>/server.{crt,key}
   ```

2. **Add the new HA env vars** to your `.env`:
   ```
   REPMGR_PASSWORD=<strong-pw>
   PGPOOL_ADMIN_PASSWORD=<strong-pw>
   # Existing REDIS_PASSWORD, DB_PASSWORD, etc. still apply.

   # mTLS opt-in (default off; flip when you're ready)
   EDUZIM_TLS_ENABLED=true
   EDUZIM_TLS_CA_CERT=/etc/eduzim-tls/ca.crt
   EDUZIM_TLS_SERVER_CERT=/etc/eduzim-tls/server.crt
   EDUZIM_TLS_SERVER_KEY=/etc/eduzim-tls/server.key
   ```

3. **Mount cert volumes** into each service container (one-time edit
   to `docker-compose.ha.yml`'s per-service `volumes:` block — left
   intentionally as a TODO so you can opt in only after the certs are
   really on disk):
   ```yaml
   academics:
     volumes:
       - ./infra/certs/ca.crt:/etc/eduzim-tls/ca.crt:ro
       - ./infra/certs/academics/server.crt:/etc/eduzim-tls/server.crt:ro
       - ./infra/certs/academics/server.key:/etc/eduzim-tls/server.key:ro
   ```
   (Repeat for identity, finance, communications, reporting-service,
   api-gateway.)

4. **Switch each service's Dockerfile CMD** to the shared serve
   helper (one-time, only when you turn on mTLS — uvicorn-flag args
   are forwarded transparently):
   ```dockerfile
   # Before (single-node baseline):
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   # After (mTLS-capable):
   CMD ["python", "-m", "eduzim_shared.serve", "app.main:app"]
   ```

## First-time HA deploy

```bash
# Build images that include the new shared modules
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml build

# Bring up data-plane components in order
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml up -d \
    pg-0 pg-1
sleep 60   # let repmgr settle

docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml up -d \
    pgpool pgbouncer
sleep 10

# Run migrations against the new pgpool endpoint
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml run --rm migrations

# Bring up Kafka cluster + UI
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml up -d \
    kafka-0 kafka-1 kafka-2 kafka-ui
sleep 30

# Bring up Redis HA
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml up -d \
    redis-master redis-replica redis-sentinel-0 redis-sentinel-1 redis-sentinel-2
sleep 15

# Bring up the rest (app services)
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml up -d
```

## Smoke tests

```bash
# Postgres cluster status — pg-0 should be primary
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml exec pg-0 \
    psql -U eduzim -d postgres -c "SELECT * FROM repmgr.show_cluster();"

# Kafka cluster — three brokers, replication factor 3
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml exec kafka-0 \
    kafka-topics --bootstrap-server kafka-0:9092 --describe

# Redis Sentinel quorum
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml exec redis-sentinel-0 \
    redis-cli -p 26379 SENTINEL masters

# mTLS — gateway should serve HTTPS on the bound port
curl -v --cacert infra/certs/ca.crt \
    --cert infra/certs/api-gateway/server.crt \
    --key infra/certs/api-gateway/server.key \
    https://localhost:8000/healthz
```

## Chaos gate

Run the suite to close the Phase 5 gate condition:

```bash
./scripts/chaos/run-all.sh
```

Expected output: 4/4 PASS. See `scripts/chaos/README.md` for individual
pass criteria.

## Rollback

If the HA overlay misbehaves, drop back to single-node:

```bash
# Stop the HA stack
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml down

# Bring up the single-node baseline
docker compose -f docker-compose.prod.yml up -d
```

Per-service `DATABASE_URL` still points at `pgbouncer:6432`, which in
single-node mode talks to `postgres:5432` directly (no pgpool). The
data in `postgres_data` is unchanged; HA-mode data lives in
`postgres_pg0_data` and `postgres_pg1_data` (separate volumes), so a
rollback resumes the pre-HA volume.

To migrate data INTO the HA cluster on first cutover, run a `pg_dump |
psql` from the old volume into the new one before flipping app services.

## Known caveats

- **pgpool transaction-mode caveats** — same as pgbouncer's; no
  prepared statements, no session-level advisory locks. We don't use
  either.
- **mTLS cert lifecycle** — currently manual via
  `scripts/generate-mtls-certs.sh`. Production should swap to
  cert-manager (k8s) or SPIFFE/SPIRE for rotation.
- **Redis sentinel + python redis client** — requires `redis>=4.0` and
  the `eduzim_shared.redis_client.from_url` wrapper. Direct
  `redis.from_url(...)` does NOT understand `redis+sentinel://`.
- **kafka-ui** is exposed on port 8090 with no auth. Lock down at the
  reverse-proxy layer in prod (Cloudflare Access / basic-auth).
- **The 7-component HA stack** uses ~5GB of RAM at idle. Single-node
  uses ~1.5GB. Budget accordingly.
