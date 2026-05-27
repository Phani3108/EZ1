# ADR 010 — Offline Conflict Resolution: LWW for Attendance/Marks, Detect+Manual for Announcements/Incidents

- **Status**: Accepted
- **Date**: 2026-05-26
- **Deciders**: Founder
- **Tags**: offline, data, ux

## Context

EduZim is offline-first. The `@eduzim/offline-core` package queues writes locally and syncs when connectivity returns. Real-world: two devices may edit the same record while offline and reconnect at different times. What to do?

Four options:

- A — Last-write-wins (LWW) by `last_modified_at`
- B — CRDTs (true mergeable types)
- C — Operational Transform (Google Docs style)
- D — Conflict detection + manual resolution

## Decision

A **mixed model**, applied per data type:

| Data | Resolution | Rationale |
|---|---|---|
| Attendance records | **LWW** by `last_modified_at` | Same student/date rarely edited by two teachers; LWW is deterministic; silent overwrite is acceptable here. |
| Marks | **LWW** | Similar pattern — usually one teacher per subject. Edge case is co-teaching; mitigated by per-subject ownership. |
| Announcements | **Detect + manual** | Announcement content is write-once intent. Two teachers crafting separate announcements is fine (they coexist). Two edits to the *same* announcement → admin reviews. |
| Disciplinary incidents | **Detect + manual** | Incident content is investigative; silent loss is unacceptable. Conflict surfaces in the admin queue. |
| Comments on marks | **LWW** | Same as marks. |
| Lesson plans | **Detect + manual** | Plans are authored work; co-edit conflicts shouldn't silently drop changes. |
| Quiz creation | **LWW per question; detect+manual on quiz metadata** | Question text changes can LWW; metadata (title, max score) is rarer and worth surfacing. |

The UX is **always** clear about which mode applies — a small "you're editing offline" indicator, and for detect+manual data, a "this was also edited elsewhere; resolve" admin view.

## Consequences

### Positive
- Most teacher hot-path writes (attendance, marks) just work — fast, deterministic, no UI friction.
- The rare-but-important cases (incidents, plans) get the visible-conflict UX they deserve.
- Implementation cost is bounded: no CRDT machinery; conflict-detection is a `last_modified_at` comparison plus a queue.

### Negative
- Silent overwrite for attendance/marks is real. Two teachers can lose an edit if both mark the same student on the same day. Mitigated by: classroom workflows don't usually overlap, audit log captures who-changed-what, an admin can reconstruct from history if a dispute arises.
- Two code paths to maintain (LWW vs detect+manual).

### Neutral
- The decision can evolve per data type. If field reports reveal silent loss is happening in attendance, we can promote attendance to detect+manual.

## Implementation Notes

- `last_modified_at` is required on every offline-syncable row. Already in place for attendance via `client_event_id` (see `services/attendance-service/`).
- Detect+manual:
  - Server compares incoming `last_modified_at` with stored.
  - If both are post-fork (i.e., they share no recent ancestor and both changed since), conflict is recorded.
  - Server stores both versions; admin sees them in a `/admin/conflicts` page (Phase 11e or Phase 13b — TBD).
  - Resolution: admin picks one or merges manually; the result becomes the canonical version with a new `last_modified_at`.
- UI affordances:
  - `<OfflineModeBadge mode="lww" />` on attendance/marks edit screens.
  - `<OfflineModeBadge mode="detect" />` on announcement/incident/plan edit screens, with a tooltip explaining what happens on conflict.

## Alternatives Considered

### B — CRDTs everywhere
**Rejected.** Overkill. Implementation complexity high; payoff low for our data shapes (mostly write-once or per-cell scoped).

### C — Operational Transform
**Rejected.** Fits real-time collaborative editing, not offline-first batch sync. Wrong tool.

### D-everywhere — Detect + manual for everything
**Rejected.** Teachers don't want to "resolve conflicts" on every attendance row. UX burden is unjustified for high-write low-conflict data.

## References

- Plan: §3 Debate 8 (resolved)
- Backlog: `task.md` §1 DEC-010, Phase 11e (incidents UI), Phase 13b (admin conflict review)
- Related code: `packages/offline-core/`, `services/attendance-service/app/services/attendance_service.py`
