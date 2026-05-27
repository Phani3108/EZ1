# ADR 015 — Self-managed HA via Bitnami stack (Phase 5)

**Status**: Accepted (Phase 5, scaffolded 2026-05-26)
**Closes (scaffolding)**: INFRA-003, INFRA-004, INFRA-005, INFRA-006, INFRA-019
**Closes (chaos-tested on staging)**: pending

## Context

Phase 5 needs production-grade HA for the four stateful components:
Postgres, Kafka, Redis, and the in-flight TLS between services. The
options space:

* **Patroni + etcd** for Postgres — industry standard, complex
  (requires running an etcd cluster). Best for k8s where StatefulSets +
  PVC management are first-class.
* **Bitnami postgresql-repmgr** — simpler 2-node setup with auto-
  promote via repmgr; pair with `bitnami/pgpool` for primary-aware
  routing. Designed for docker-compose / k8s without an etcd dep.
* **AWS RDS Multi-AZ** — eliminates the operational burden entirely;
  the price is data-residency lock-in to whichever AWS region we choose
  (Debate 5 still open; Cape Town vs Mumbai vs on-prem Zimbabwean
  hosting all have different trade-offs).
* **CockroachDB / TiDB / YugabyteDB** — distributed-by-design; massive
  jump in operational complexity and licensing concerns.

For Kafka the live decision is KRaft (single quorum, no Zookeeper) vs
classic ZK-based. KRaft is the right answer for any greenfield in 2025+
— Zookeeper is deprecated.

For Redis: Sentinel (1 primary, 1+ replicas, sentinel quorum) vs
Cluster (sharded) vs hosted (ElastiCache / Upstash). Cluster only
matters at a key-count we won't see for years. Sentinel is the right
answer for an HA cache tier of our size.

For service-to-service auth: mTLS (cert-based, classical) vs SPIFFE/SPIRE
(workload identity, industry-leading) vs HMAC-over-headers (our PH3
gateway token, simplest). mTLS adds defence-in-depth on top of PH3
without requiring a new control plane.

## Decision

For the **self-managed HA path** (this ADR's scope):

* **Postgres** — bitnami/postgresql-repmgr 2-node + bitnami/pgpool.
  No etcd. Auto-promotion via repmgr. pgpool routes writes to the
  current primary.
* **Kafka** — 3-broker KRaft cluster. `replication.factor=3`,
  `min.insync.replicas=2`. kafka-ui at :8090 for observability.
* **Redis** — Sentinel topology with 3 sentinels (quorum 2), 1
  primary, 1 replica. Application reads use a new
  `redis+sentinel://...?master=mymaster` URL scheme parsed by
  `eduzim_shared.redis_client.from_url`.
* **mTLS** — self-signed CA + per-service leaf certs. CA cert + each
  service's leaf cert mounted at `/etc/eduzim-tls/`. Wired via
  `eduzim_shared.mtls.uvicorn_kwargs()` (server side) and
  `eduzim_shared.mtls.httpx_kwargs()` (client side). Opt-in via
  `EDUZIM_TLS_ENABLED=true`.

For the **hosted alternative path** (kept as a documented option, not
the default):

* AWS RDS Multi-AZ for Postgres, ElastiCache for Redis, MSK for Kafka.
* mTLS replaced by AWS PrivateLink + VPC SG ingress rules.
* Tradeoff: lock to one AWS region; cheaper to operate; pending
  Debate 5 (data residency) before adoption.

The HA stack is composed via `docker-compose.ha.yml` overlaying
`docker-compose.prod.yml`. Single-node prod still works for low-stakes
deployments; HA mode is opt-in via the overlay.

## Why not Patroni

* Adds etcd as a hard dependency. We don't otherwise need etcd.
* The Bitnami repmgr image meets the same `failover < 60s` SLA target
  with a far smaller compose footprint (2 postgres nodes + pgpool vs
  3 etcd + 2 postgres + Patroni sidecar).
* When we move to k8s (Phase 7+), Patroni-via-CrunchyData-Operator
  becomes the easy default. At that point the docker-compose decision
  is moot — replace the whole compose layer with k8s manifests.

## Why not hosted-first

* Debate 5 (data residency) hasn't resolved. Pre-committing to AWS
  region locks us in before that decision.
* Self-managed validates the application's "this thing can survive
  Postgres failover" assumption in our own environment — useful even
  if we move to RDS later.
* Cost: at the scale we're targeting (single-school pilots), hosted
  managed-DB has a high fixed cost (RDS Multi-AZ ≈ $200+/mo for a
  small instance). Self-managed on a single VPS is ~$10/mo.

## Why mTLS (and not just the PH3 X-Gateway-Token)

* The PH3 token is a shared secret across all services. If any one
  service container is compromised, the token leaks and the attacker
  can impersonate the gateway to all others.
* mTLS pins the IDENTITY of each caller per cert. A compromised
  academics container has only academics's cert; impersonation requires
  forging a cert signed by the shared CA.
* Defence in depth: PH3 still applies. An attacker needs to bypass
  BOTH layers.

## Consequences

* Single-node `docker-compose.prod.yml` deploys cost 1.5GB RAM; HA
  overlay costs ~5GB RAM. Budget node sizing accordingly.
* `eduzim_shared.redis_client.from_url` is now the canonical way to
  build redis clients. The gateway has been updated; future services
  that need Redis must use this helper (not `redis.from_url` directly).
* The mTLS scripts and library are scaffolded but NOT yet on by
  default. Operators enable per-deploy by setting `EDUZIM_TLS_ENABLED=true`
  and switching the Dockerfile CMD to `python -m eduzim_shared.serve`.
* Chaos tests (`scripts/chaos/`) are scaffolded but require real Docker
  to run — they're the Phase 5 gate condition, validated on staging
  before the items in `task.md §3 Phase 5` flip from "scaffolded" to
  "closed".

## Migration notes

* First HA cutover: dump `postgres_data` and reload into the new
  `postgres_pg0_data` volume. See the rollout runbook for exact commands.
* Kafka switchover doesn't preserve offsets across the broker swap
  (single → three brokers with different broker IDs). Plan a brief
  window where consumers re-process from the head — the reporting
  consumer's idempotency inbox (ProcessedEvent) handles replay
  correctly. Other Kafka consumers should be audited.
* Redis switchover loses all in-flight data (rate-limit counters,
  cached lookups). All Redis use in EduZim is intentionally
  best-effort, so a moment of cold cache is fine.
