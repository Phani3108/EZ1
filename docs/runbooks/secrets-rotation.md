# Secrets Rotation Runbook

> **Scope**: how secrets enter EduZim, how to rotate them safely, how to recover from a leak.
> **Related**: BUG-003 (default JWT secret in compose), BUG-004 (default internal service token), INFRA-013 (secrets workflow), ADR 005 (data residency), ADR 007 (privacy-by-design).
> **Status**: dev workflow live as of 2026-05-26. Production workflow (AWS Secrets Manager / Vault) is planned in Phase 5 / Phase 17 of `task.md` — this runbook documents the *interim* posture and the production target.

---

## What secrets exist

| Secret | Used by | Source today |
|---|---|---|
| `JWT_SECRET_KEY` | all services (issuing + validating access/refresh tokens) | `.env` (local dev) / env var (prod) |
| `INTERNAL_SERVICE_TOKEN` | service-to-service `/internal/*` calls (e.g., `attendance-service` → `school-service` teacher-class authz) | `.env` (local dev) / env var (prod) |
| `DB_PASSWORD` | Postgres connection strings inside docker-compose | `.env` |
| `PAYNOW_INTEGRATION_KEY` | Paynow webhook HMAC + initiation | env var (per-school in future per ADR 004) |
| `AFRICASTALKING_API_KEY` | SMS sends (planned Phase 12c) | env var |
| `FCM_SERVER_KEY` | push notifications (planned Phase 12c) | env var |
| `SMTP_PASSWORD` | outbound mail | env var |
| Postgres connection password (inside `DATABASE_URL`) | each service's DB connection | env var or compose interpolation |

---

## Local development

### First-time setup

```bash
./scripts/bootstrap-secrets.sh
docker compose up -d
```

`bootstrap-secrets.sh` generates strong random values for `JWT_SECRET_KEY`,
`INTERNAL_SERVICE_TOKEN`, and `DB_PASSWORD`, writes them to `.env` (chmod 600,
gitignored), and configures the dev flags. `docker compose` then picks up
`.env` automatically.

### Rotate (developer machine)

```bash
./scripts/bootstrap-secrets.sh --rotate
docker compose down
docker compose up -d
```

The `--rotate` flag refuses to overwrite without confirmation and backs up the
previous `.env` to `.env.YYYYMMDD-HHMMSS.bak`. After rotation, running
services will reject all tokens issued before the rotation — users must log
in again.

### Check status

```bash
./scripts/bootstrap-secrets.sh --check
```

Lists each required secret as `present`, `KNOWN-BAD`, or `MISSING`. CI should
invoke this before any deployment.

### Why no defaults in `config.py` anymore

Pre-2026-05-26, every service's `config.py` carried a default
(`dev-jwt-secret-change-in-production`, `change-me-in-production`, etc.). The
audit found these committed to git. A deployment that forgot to set the env
var inherited the default — and the default was public.

Now:

- `JWT_SECRET_KEY: str` (no default) — pydantic raises a `ValidationError` at
  startup if missing.
- `INTERNAL_SERVICE_TOKEN: str` (no default) — same.
- `docker-compose.yml` uses `${VAR:?...}` interpolation — compose fails with a
  clear message if the env is unset.
- The gateway has an extra runtime guard that refuses to start when
  `JWT_SECRET_KEY` matches any historic dev/test value (see
  `services/api-gateway/app/main.py`).

Test runs are unaffected: each service's `tests/__init__.py` calls
`os.environ.setdefault(...)` with an obvious-test value so the config loads in
test contexts.

---

## Production

### Source of truth

Production secrets live in a managed secret store, not in `.env`. Phase 5 /
Phase 17 of `task.md` deliver the wiring. Target stores:

- **AWS Secrets Manager** (current target; ADR 005 hosts us in AWS Cape Town
  for v1).
- **HashiCorp Vault** (alternative; revisit if we move off AWS in Year 2 per
  ADR 005's migration commitment to a Zimbabwean provider).

Until that wiring lands, an interim production deploy uses environment
variables injected by the deployment pipeline (GitHub Actions Secrets →
container env). This is acceptable for staging / pilot, not for general
availability.

### Rotation cadence

- **JWT_SECRET_KEY**: 90 days OR immediately on suspected compromise.
- **INTERNAL_SERVICE_TOKEN**: 90 days OR immediately on suspected compromise.
- **Provider API keys (Paynow, Africa's Talking, FCM)**: per provider's
  recommended cadence; minimum quarterly.
- **DB password**: 180 days; rotation requires coordinated app + DB change.

### Production rotation procedure (JWT_SECRET_KEY)

JWT_SECRET_KEY rotation is **disruptive** — all in-flight access tokens
become invalid. Procedure:

1. **Announce** in #ops at least 24 hours ahead (or immediately for incident).
2. **Stage**: rotate in staging first, verify auth still works end-to-end.
3. **Generate** new value: `openssl rand -hex 64`.
4. **Store** in AWS Secrets Manager (or current vault). Tag with rotation
   timestamp. Keep prior value tagged `previous-1` for emergency rollback.
5. **Deploy** services in this order, draining between steps:
   - identity / auth (must be first — it's the issuer)
   - api-gateway (must validate freshly-issued tokens)
   - all other services
6. **Verify**: hit `/api/v1/auth/login` from a test account, confirm new token
   works and old token returns 401.
7. **Force re-login**: optionally clear `eduzim_rt` cookies via deploy or
   leave for natural attrition (max 30 days per cookie TTL).
8. **Monitor**: 401 rate spike for ~5 min is expected; should subside as
   users re-authenticate.
9. **Document** in `docs/runbooks/changelog.md` with rotation timestamp.

### Production rotation procedure (INTERNAL_SERVICE_TOKEN)

Less disruptive than JWT — only affects internal service-to-service calls.

1. Generate new value: `openssl rand -hex 32`.
2. Update the secret in vault.
3. Deploy all services with `/internal/*` endpoints simultaneously (i.e., in
   one orchestrated deploy). They share one secret; mixing old + new breaks
   internal authz.
4. Verify: hit a flow that triggers an internal call (e.g., teacher attendance
   sync → `school-service` authz check).

Future improvement (planned in Phase 5): support two valid tokens at once
(active + grace-period prior) so rotation is online without a synchronised
restart.

---

## Incident response: secret leak

If a secret is suspected leaked (e.g., found in a screenshot, a git push, a
log dump):

1. **Treat as confirmed.** Don't wait for proof.
2. **Notify** the on-call channel immediately.
3. **Rotate** following the procedures above. JWT_SECRET_KEY is the most
   urgent — every issued token is suddenly forgeable.
4. **Audit logs** (Phase 9 `audit_log` table) for the time window between
   suspected leak and rotation. Look for:
   - logins from unusual IPs
   - elevation-of-role events
   - cross-tenant access patterns
5. **Notify DPO** (per ADR 007) if any PII was likely exposed.
6. **Notify Ministry / school customers** per the contractual SLA in any
   pilot agreement.
7. **Post-mortem** within 48 hours. Document in `docs/runbooks/incidents/`.

If the leaked secret reached a public git history:

- Rewrite history is **not** sufficient (mirrors retain). Rotate is the only
  real mitigation.
- Once rotated, the leaked value is worthless to attackers (assumes the rotate
  fully replaced it — verify with `bootstrap-secrets.sh --check`).

---

## What the gateway will refuse to do (defence in depth)

`services/api-gateway/app/main.py` enforces, at startup:

- Refuses to start with `DEBUG=False` if `JWT_SECRET_KEY` is in the
  `_KNOWN_BAD_SECRETS` set (includes the historic dev/test strings).
- Refuses to start with `DEBUG=False` if `JWT_SECRET_KEY` is shorter than 32
  characters.
- Logs a warning (does not fail) for short or known-bad values in DEBUG mode
  — so local dev still works.

If a deployment hits these guards, **do not** work around them. Generate a
proper secret.

---

## Open items (tracked in `task.md`)

- **INFRA-013** — this runbook (closed by writing this file).
- **Phase 5** — Patroni / RDS Multi-AZ + Vault / Secrets Manager wiring.
- **Phase 17** — CI/CD pipeline reads secrets from vault, not env files.
- Future: support two-token grace period for `INTERNAL_SERVICE_TOKEN` rotation.
- Future: HSM-backed JWT signing for high-security tenant tiers (ADR 009
  `dedicated` tier).
