# Phase 5 chaos test suite

These scripts verify the HA gate from `task.md §3 Phase 5`:

> Chaos tests pass: kill 1 Kafka broker (system stays available); kill
> Postgres primary (failover < 60s); kill Redis primary (no observable
> user impact). All services restart cleanly with SIGTERM.

Each script is **destructive** to its target component — run only on
staging (`docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml`).
They expect the HA overlay stack to be up.

## Scripts

| Script | What it does | Pass criteria |
|---|---|---|
| `kill-pg-primary.sh` | Stops the `pg-0` container; expects pgpool to detect failure and route writes to `pg-1` (auto-promoted by repmgr). | A write through `pgbouncer:6432/auth_db` succeeds within 60s of the kill. |
| `kill-kafka-broker.sh` | Stops `kafka-1` (one of three brokers). Existing Kafka consumers must keep receiving events from the surviving brokers. | A consumer offset advances during the 30s observation window after the kill. |
| `kill-redis-primary.sh` | Stops `redis-master`. The 3-sentinel quorum must promote `redis-replica` within ~10s; gateway rate-limit calls must keep working. | A GET to `/api/v1/auth/login` (which hits Redis for rate-limit) returns within 5s after the failover. |
| `sigterm-services.sh` | Sends SIGTERM to each app service in turn. Each must drain in-flight requests and exit ≤ 5s. | The shutdown lifespan logs "Service X shutdown complete" within 5s for every service. |

## Usage

```bash
# Bring up the HA stack on staging
docker compose -f docker-compose.prod.yml -f docker-compose.ha.yml up -d
sleep 60   # let the cluster settle

# Run a single chaos test
./scripts/chaos/kill-pg-primary.sh

# Or run the whole suite (sequential, with delays between)
./scripts/chaos/run-all.sh
```

The scripts return:
- `0` — chaos test passed
- `1` — pass criterion not met
- `2` — script setup failed (couldn't reach a precondition)

## What's NOT covered (yet)

- Network partition tests (`iptables -A INPUT -s pg-0 -j DROP`). Add in
  Phase 7 with a proper chaos-engineering tool (Litmus / Chaos Mesh).
- Multi-component failure (kill pg-0 + kafka-1 simultaneously). Add
  once each single-component test passes.
- Disk-full / OOM scenarios. Add via cgroup limits in Phase 7.
