# ADR 006 — Consolidate from 8 Microservices to 4

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: architecture, backend, operations

## Context

The current build has 8 backend services (`auth`, `school`, `student`, `attendance`, `fees`, `communication`, `assessment`, `reporting`) plus an API gateway. The audit flagged this as over-engineered for the present team size and operational maturity:

- 8 Dockerfiles, 8 databases, 8 migration paths, 8 deployment risks.
- Latency added by cross-service HTTP calls in hot paths (e.g., parent-child authorization).
- JWT re-parsed in 7 of 8 services (also addressed in ADR for Phase 3 work).
- No team yet to staff one service per team-of-2.

Three options were debated:

- A — Keep 8 services
- B — Consolidate to 4 along domain boundaries
- C — Modular monolith

## Decision

Consolidate to **four services**, plus the API gateway, plus an asynchronous reporting consumer:

| Service | Merges | Responsibility |
|---|---|---|
| `identity` | `auth-service` + RBAC pieces of `school-service` | Auth, users, roles, permissions, sessions, tokens |
| `academics` | `school-service` + `student-service` + `attendance-service` + `assessment-service` | School, classes, subjects, terms, students, parents, enrollments, attendance, marks, lesson plans, quizzes |
| `finance` | `fees-service` (+ payment provider wiring per ADR 004) | Fee structures, invoices, payments, financial dashboards |
| `communications` | `communication-service` (+ notification provider wiring per ADR 004) | Announcements, threads, outbox, notifications |
| `reporting` (async consumer) | `reporting-service` rewritten | Kafka consumer projecting events into a read-optimised projection DB; no HTTP API |

The API gateway routes to the four HTTP services. The reporting consumer reads from Kafka topics emitted by the four services; the read API for reports goes through one of the HTTP services (likely `academics`) hitting the projection DB.

## Consequences

### Positive
- Halved operational surface. 4 service binaries, 4 databases.
- Domain boundaries match how features cluster (everything academic is in one place; finance is its own place).
- Easier to reason about: parent-child authz is no longer a cross-service RPC inside `academics`.
- Reporting becomes a true projection — read-write separation done right.

### Negative
- ~3-week refactor with full test-suite rework. Real cost.
- Bigger blast radius per service: an `academics` regression touches more functionality than the prior fine-grained `attendance-service` regression.
- Some endpoints inherit subtler internal coupling (e.g., enrollment authorization sits inside academics, used by attendance and assessment paths — must be cleanly modularised internally).

### Neutral
- The 4-service shape leaves room to split back out later if a specific domain grows (e.g., `academics` could split into `academics-write` and `academics-read` if write throughput dominates).

## Implementation Notes

- **Order matters.** This must happen *before* Phase 11 onwards (persona features), otherwise we refactor a much bigger codebase later.
- Migration plan: code-level merge first (one repo's modules become directories in the new service), database merge second. Keep the existing DBs initially; collapse `auth_db + school_db` into `identity_db` and `school_db + student_db + attendance_db + assessment_db` into `academics_db` as separate sub-tasks.
- Gateway route table (`services/api-gateway/app/routes.py`) updates to point at the new service URLs.
- Frontend `api-client` updates if any service URLs are hardcoded (most use gateway prefix `/api/v1/...`, which doesn't change).
- All test files retargeted to the new service-level layout. Cross-tenant isolation tests added during the consolidation, per `task.md` Q-006.
- The reporting consumer runs as a separate container without an HTTP port; its health is exposed via a sidecar `/health` endpoint.

## Alternatives Considered

### A — Keep 8 services
**Rejected.** The operational overhead is real and unjustified at current team size. The "future team scale" argument doesn't apply when there isn't a team yet.

### C — Modular monolith
**Rejected.** Throws away too much of the existing structural work (Kafka boundaries, idempotency tables, per-service migrations). The refactor cost to get from 8 services to a monolith is higher than the consolidation to 4, and we lose the option to split a hot service back out later.

## References

- Plan: §3 Debate 3 (resolved)
- Backlog: `task.md` §1 DEC-006, Phase 2 tasks PH2-1 through PH2-10
- Related ADRs: 004 (provider interfaces live inside the services they belong to), 007 (privacy review of merged schemas)
