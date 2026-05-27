# ADR 022 — Curriculum, Question Bank & Content Templates (Phase 16)

**Status**: Accepted 2026-05-27
**Closes**: Phase 16 — academic-content layer (curriculum, ZIMSEC reference, topic↔resource cross-index, question bank with auto-grading, homework + lesson-plan templates, attachment polish, teacher/admin/ministry UI)
**Builds on**: ADR 018 (audit invariants), ADR 020 (Ministry-inside-admin-web + cross-school sentinel), ADR 021 (Provisioner role + onboarding draft pattern)

## Context

Phase 15 closed the "from zero to live" onboarding pipeline — schools can now import students, teachers, parents, and fee structures via CSV + invite-flow. What it didn't address is the **academic-content layer** that comes after Go Live: how a teacher actually injects subjects, curriculum, syllabus indexes, assignments, and exam papers — and how that content is reused across teachers and classes.

The exploration (Phase 1) confirmed how thin the pre-existing state was:

* `Subject` was only `(school_id, name, code, is_active)` — no grade level, no curriculum tie.
* No `Unit`, `Topic`, `Chapter`, `Curriculum`, or `LearningOutcome` model existed.
* No `Question`, `QuestionBank`, or `ExamPaper` model existed — `Assessment` was metadata-only (type enum + max_marks). No `description`, no `instructions`, no exam-paper attachment hook.
* `LessonPlan` had objectives / activities / resources text columns but no attachment hook and no topic link. `Homework` had a text body + a separate polymorphic `Attachment` table but no template or share-to-other-classes action.
* Polymorphic `Attachment` (Phase 11b T-008) was the right primitive for files / images / audio — 10 MB cap, conservative MIME allowlist that excluded Office formats and CSV.
* No Ministry-level "national curriculum" reference data. Schools typed subjects from scratch.

Phase 16 adds the missing structure. **It does NOT ship the real ZIMSEC content** — that's a separate, ongoing curriculum-team activity. The platform supports importing real ZIMSEC content via CSV / Excel (Ministry-side bulk endpoint) and a small sample-data seeder (`scripts/import_zimsec.py`) demonstrates the end-to-end flow with placeholder rows.

## Decisions

### 1. "Indexes" = curriculum hierarchy AND a Topic→Resource cross-index

Two layers:

* **Curriculum hierarchy**: Subject → Unit → Topic → optional Subtopic (one level deep via `parent_topic_id`). Subjects carry `grade_levels` (JSON array). Units carry their own `grade_level`. Topics carry `learning_outcomes` (free text).
* **Topic→Resource cross-index**: every `LessonPlan`, `Homework`, `Assessment`, `FormativeAssessment`, and `Question` carries a `topic_ids` (JSON text) column. The endpoint `GET /api/v1/curriculum/topics/{id}/resources` returns the inverse — every row that mentions a given topic. The `GET /api/v1/curriculum/coverage?subject_id=X` endpoint produces per-topic counts so HoDs can spot under-tagged areas.

For v16 the cross-index is implemented as a `LIKE '%"<uuid>"%'` substring scan against the JSON-text column. On Postgres with JSONB this would ideally be a GIN index — that's a Phase 17 swap. The same code path works on SQLite for tests + dev.

### 2. Ingestion: Ministry ZIMSEC reference seeded once; schools adopt

Decision locked during Phase 16 planning. EduZim Operations (or Ministry+Provisioner) seeds the ZIMSEC syllabus into `national_subjects` / `national_units` / `national_topics` via `POST /api/v1/ministry/bulk/national-curriculum` (a CSV bulk endpoint mirroring the school-local one). Each school clicks "Adopt" on `POST /api/v1/curriculum/adopt-subject`; the entire unit + topic tree clones into the school's local `Unit` + `Topic` tables, with `national_unit_id` / `national_topic_id` back-references preserved.

Idempotency: re-adopting is a no-op (returns `idempotent: true` + zero clone counts). Custom topics outside the ZIMSEC tree remain supported via the school-local CSV importer + manual `POST /curriculum/{units,topics}`.

### 3. Question bank — mid scope

`Question`, `QuestionOption`, `QuestionDraft` models. Types: `MCQ`, `TRUE_FALSE`, `SHORT_ANSWER`. Drafts mirror the Phase 15 `StudentDraft` pattern — teachers submit (new `question:draft` permission, granted to Teacher), HoD / SchoolAdmin approves to publish.

`Assessment` is extended with `description`, `instructions`, `question_ids` (JSON array), and `exam_paper_attachment_id` (nullable, references an `Attachment` row in communications).

`POST /api/v1/assessments/{id}/compose` binds question IDs (validated to be in the caller's school + status=`published`). `POST /api/v1/assessments/{id}/auto-grade` accepts a student's `{question_id, response}` list and:

* MCQ: matches `response` against the option labels with `is_correct=true`.
* TRUE_FALSE: case-insensitive compare against `correct_answer_text` (`"true"` / `"false"`).
* SHORT_ANSWER: case-insensitive, trim-on-both-sides compare.

Score = `(correct / total_bound) * max_marks`, upserted into the student's `Mark` row. Question analytics counters (`attempts_count`, `correct_count`) tick on each grade.

Long-form essays + scanned past papers ride on `exam_paper_attachment_id` and stay manual — that's the explicit "mid scope" choice.

### 4. Sharing — Template library, not clone-everywhere

`HomeworkTemplate` and `LessonPlanTemplate` live in a per-school library, owned by `maintained_by_user_id`. HoDs publish a template school-wide (`POST /{template-type}/{id}/publish-school-wide`); other teachers instantiate via `POST /{template-type}/{id}/instantiate` → a real `Homework` / `LessonPlan` row is created with `template_source_id` / `template_id` set. `POST /homework/{id}/sync-from-template` pulls title + description + topic tags back from the source.

Attachment cloning at instantiation time is **deliberately deferred to Phase 17** — the instance row's `attachments_cloned` audit detail is `0` for v16 and the operator re-attaches files. Documented here so it's not a surprise.

### 5. Attachment + storage polish (Phase 16e)

* MIME allowlist extended with the four Office MIMEs + `text/csv`. Teachers can now attach `.xlsx` worksheets and `.docx` lesson handouts directly; admins can attach `.csv` when the bulk-import flow isn't convenient.
* Size cap bumped 10 MB → 25 MB so a long-form scanned exam-paper PDF round-trips.
* `VALID_OWNER_KINDS` extended with `homework`, `lesson_plan`, `lesson_plan_template`, `homework_template`, `assessment`, `question`, `topic`, `national_topic`.

OCR for scanned PDFs / images is **Phase 17**. Image thumbnails are **Phase 17**. ADR-018 invariants still apply.

## Audit invariants (per ADR 018, reaffirmed)

| Event | Target | Details |
|---|---|---|
| `curriculum.unit.created` | `{school_id, subject_id, unit_id}` | `{has_national_ref}`. No names. |
| `curriculum.topic.created` | `{school_id, subject_id, topic_id}` | `{has_parent, has_national_ref}`. No name. |
| `curriculum.subject.adopted` | `{school_id, subject_id, national_subject_id}` | `{units_cloned, topics_cloned}`. Counts only. |
| `national_curriculum.subject.{created,published}` | `{national_subject_id}` | `{country}`. No name. School_id = cross-school sentinel. |
| `national_curriculum.{unit,topic}.created` | `{national_*_id}` | `{has_parent}`. No name. |
| `question.created` | `{school_id, subject_id, question_id}` | `{type, difficulty}`. No text, no answer. |
| `question.draft.submitted` / `.approved` / `.rejected` | same shape | rejection_reason allowed on reject (200-char cap; admin-supplied). |
| `assessment.composed` | `{school_id, assessment_id}` | `{question_count, has_exam_paper_pdf}`. |
| `assessment.auto_graded` | `{school_id, assessment_id}` | `{question_count, correct_count, graded_questions}`. No student answers. |
| `template.created` / `.published_school_wide` / `.unpublished_school_wide` / `.instantiated` / `.synced_from_source` | IDs + `template_type` | `{has_subject, class_id, attachments_cloned}` as applicable. No titles, no bodies. |

The only place an admin-supplied free text legitimately reaches audit details is `rejection_reason` on draft endpoints (now expanded to include `question.draft.rejected` alongside the Phase 15 student/parent drafts).

## What this ADR does NOT decide

* **Real ZIMSEC content**: out of scope; lives outside the codebase; gets imported by EduZim Operations via CSV / Excel. `scripts/import_zimsec.py` ships 3 placeholder subjects for dev/test only.
* **Attachment cloning** on template instantiate — Phase 17. Tracked in `task.md`.
* **OCR for scanned PDFs / images** — Phase 17 (Tesseract integration).
* **Image thumbnail server-side** — Phase 17 (Pillow resize).
* **Curriculum versioning** — when a Ministry curriculum review publishes v2, schools that adopted v1 need a controlled upgrade path. Phase 17+.
* **Cross-school template sharing** — currently templates are per-school. NGO use-case for distributing canonical templates across schools is Phase 18.
* **Essay auto-grading** — Phase 18 (rubric or LLM-assisted).
* **ZIMSEC API integration** — if/when ZIMSEC publishes an authoritative feed, we replace the CSV-import flow. Until then, manual CSV is canonical.

## Consequences

### Positive
* A teacher can submit a question, the HoD reviews, and the question becomes reusable across every assessment. Auto-grading slashes the marking workload for objective questions.
* A teacher can publish a homework template; every other teacher in the same subject can instantiate it for their class with one click.
* Schools "adopt" the ZIMSEC syllabus once and get the full tree mirrored locally — no per-school re-keying of the national curriculum.
* The Topic↔Resource cross-index gives HoDs a coverage view: "which of our topics has zero teacher attention?"

### Negative
* The `topic_ids` JSON-text column with substring LIKE is O(N) per topic query. Fine for v16 scale (per-school N ≤ a few thousand resources); a Phase 17 swap to Postgres JSONB + GIN index is the upgrade path.
* Attachment cloning on template instantiation is not yet implemented; instance creators re-attach files. Documented; not a silent gap.
* Question-bank text + answers are stored on the `Question` row in plaintext. ADR 018 keeps them out of audit details, but the row itself is queryable by anyone with `school:manage`. Acceptable: questions are not personal data; they're school IP at most. If a school marks the bank confidential, the existing `archived_at` soft-delete + RBAC are the lever.
