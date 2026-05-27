"""
import_zimsec.py — Phase 16a stub seeder for the NationalCurriculum.

⚠️ THIS IS SAMPLE DATA, NOT THE REAL ZIMSEC SYLLABUS.
=====================================================

EduZim does not — and should not — ship the official Zimbabwe ZIMSEC
syllabus content baked into source code. The actual curriculum is a
living document maintained by the Ministry of Primary and Secondary
Education; it changes with each curriculum review and is too large to
hard-code anyway.

What this script does:
  - Inserts 2–3 sample NationalSubjects (Mathematics, English, Combined
    Science — each at Form 1 level).
  - Each subject gets 2 units, each unit gets 2 topics.
  - Marks all subjects as published so the school-side adoption flow
    can be exercised in dev/test.

What it does NOT do:
  - Cover every grade level (Forms 1–6 ECD up to A-Level).
  - Cover every ZIMSEC subject.
  - Reflect any official ZIMSEC publication date or learning-outcome
    text. The `learning_outcomes` fields here are placeholders.

How to seed real ZIMSEC content (production):
  1. Get the official ZIMSEC syllabus as a CSV or Excel file.
  2. Sign in to admin-web as EduZimOps / Ministry+Provisioner.
  3. Go to /ministry/curriculum/import (Phase 16h).
  4. Upload the CSV. Bulk importer at
     `POST /api/v1/ministry/bulk/national-curriculum` handles
     upsert-idempotency on `(country, subject_code)` + `(subject_id,
     unit_code)` + `(unit_id, topic_code)` — re-runnable safely.

Usage (dev/test):
    python scripts/import_zimsec.py [--db-url postgresql://...]

The script is idempotent. Re-running is safe.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timezone


# Path setup so the script can import the academics service modules.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "services", "academics"))
sys.path.insert(0, os.path.join(REPO_ROOT, "shared"))


# Set safe env so importing the academics app doesn't blow up. These
# defaults are overridden if the operator passes --db-url.
os.environ.setdefault("DATABASE_URL", "sqlite:///./eduzim_dev.db")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("JWT_SECRET_KEY", "dev-jwt-secret-import-zimsec")
os.environ.setdefault(
    "INTERNAL_SERVICE_TOKEN",
    "test-internal-token-DO-NOT-USE-IN-PRODUCTION",
)


# ─── Sample data (NOT the real ZIMSEC syllabus) ────────────────────


SAMPLE = [
    {
        "country": "ZW",
        "code": "ZIM-MATH-FRM1",
        "name": "Form 1 Mathematics",
        "description": (
            "Sample placeholder. Replace with the real ZIMSEC Form 1 "
            "Mathematics syllabus before any school adopts."
        ),
        "units": [
            {
                "code": "U-NUM",
                "name": "Numbers",
                "sequence_order": 1,
                "grade_level": "Form 1",
                "topics": [
                    {
                        "code": "T-INT",
                        "name": "Integers",
                        "sequence_order": 1,
                        "learning_outcomes": (
                            "Add, subtract, multiply and divide "
                            "integers; recognise positive and negative "
                            "numbers in context."
                        ),
                    },
                    {
                        "code": "T-FRAC",
                        "name": "Fractions and Decimals",
                        "sequence_order": 2,
                        "learning_outcomes": (
                            "Convert between fractions and decimals; "
                            "perform the four operations on both."
                        ),
                    },
                ],
            },
            {
                "code": "U-ALG",
                "name": "Algebra",
                "sequence_order": 2,
                "grade_level": "Form 1",
                "topics": [
                    {
                        "code": "T-EXPR",
                        "name": "Algebraic Expressions",
                        "sequence_order": 1,
                        "learning_outcomes": (
                            "Simplify expressions; substitute values; "
                            "combine like terms."
                        ),
                    },
                    {
                        "code": "T-LIN",
                        "name": "Linear Equations",
                        "sequence_order": 2,
                        "learning_outcomes": (
                            "Solve linear equations in one variable; "
                            "translate word problems into equations."
                        ),
                    },
                ],
            },
        ],
    },
    {
        "country": "ZW",
        "code": "ZIM-ENG-FRM1",
        "name": "Form 1 English Language",
        "description": (
            "Sample placeholder. Replace with the real ZIMSEC Form 1 "
            "English Language syllabus before any school adopts."
        ),
        "units": [
            {
                "code": "U-READ",
                "name": "Reading and Comprehension",
                "sequence_order": 1,
                "grade_level": "Form 1",
                "topics": [
                    {
                        "code": "T-NARR",
                        "name": "Narrative Texts",
                        "sequence_order": 1,
                        "learning_outcomes": (
                            "Identify plot, setting, characters and "
                            "theme in short stories."
                        ),
                    },
                    {
                        "code": "T-INFO",
                        "name": "Informational Texts",
                        "sequence_order": 2,
                        "learning_outcomes": (
                            "Skim and scan for key information; "
                            "identify the main idea of a paragraph."
                        ),
                    },
                ],
            },
            {
                "code": "U-WRITE",
                "name": "Writing",
                "sequence_order": 2,
                "grade_level": "Form 1",
                "topics": [
                    {
                        "code": "T-PARA",
                        "name": "Paragraph Writing",
                        "sequence_order": 1,
                        "learning_outcomes": (
                            "Write a paragraph with a topic sentence, "
                            "supporting sentences, and a conclusion."
                        ),
                    },
                    {
                        "code": "T-LETTER",
                        "name": "Informal Letter Writing",
                        "sequence_order": 2,
                        "learning_outcomes": (
                            "Write an informal letter with an "
                            "appropriate greeting, body, and closing."
                        ),
                    },
                ],
            },
        ],
    },
    {
        "country": "ZW",
        "code": "ZIM-SCI-FRM1",
        "name": "Form 1 Combined Science",
        "description": (
            "Sample placeholder. Replace with the real ZIMSEC Form 1 "
            "Combined Science syllabus before any school adopts."
        ),
        "units": [
            {
                "code": "U-BIO",
                "name": "Living Things",
                "sequence_order": 1,
                "grade_level": "Form 1",
                "topics": [
                    {
                        "code": "T-CELL",
                        "name": "Cells",
                        "sequence_order": 1,
                        "learning_outcomes": (
                            "Identify the basic parts of a cell; "
                            "distinguish plant cells from animal cells."
                        ),
                    },
                ],
            },
            {
                "code": "U-PHYS",
                "name": "Matter and Energy",
                "sequence_order": 2,
                "grade_level": "Form 1",
                "topics": [
                    {
                        "code": "T-STATES",
                        "name": "States of Matter",
                        "sequence_order": 1,
                        "learning_outcomes": (
                            "Distinguish solid, liquid and gas; "
                            "describe melting, freezing, evaporation, "
                            "condensation."
                        ),
                    },
                ],
            },
        ],
    },
]


def _utcnow():
    return datetime.now(timezone.utc)


def seed(database_url: str | None = None, *, publish: bool = True,
         dry_run: bool = False) -> dict:
    """Insert sample ZIMSEC data. Returns counts.

    Args:
        database_url: optional override; otherwise reads from env.
        publish: when True, marks every inserted subject as published
                 so schools can adopt immediately. Default True for
                 dev convenience.
        dry_run: when True, does not commit.
    """
    if database_url:
        os.environ["DATABASE_URL"] = database_url

    # Late imports so env is set first.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base  # noqa
    import app.models  # noqa — ensures every model is registered

    from app.models.national_curriculum import (
        NationalSubject, NationalUnit, NationalTopic,
    )

    eng = create_engine(os.environ["DATABASE_URL"])
    # Best-effort create-all for SQLite paths. For Postgres, this is a
    # no-op when the Alembic migration has already run.
    if "sqlite" in os.environ["DATABASE_URL"]:
        Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(bind=eng)

    counts = {
        "subjects_created": 0,
        "subjects_skipped": 0,
        "units_created": 0,
        "units_skipped": 0,
        "topics_created": 0,
        "topics_skipped": 0,
        "published": 0,
    }

    with SessionLocal() as s:
        for subj in SAMPLE:
            ns = (
                s.query(NationalSubject)
                .filter(
                    NationalSubject.country == subj["country"],
                    NationalSubject.code == subj["code"],
                )
                .first()
            )
            if ns:
                counts["subjects_skipped"] += 1
            else:
                ns = NationalSubject(
                    id=uuid.uuid4(),
                    country=subj["country"],
                    code=subj["code"],
                    name=subj["name"],
                    description=subj["description"],
                )
                s.add(ns)
                s.flush()
                counts["subjects_created"] += 1

            if publish and not ns.ministry_published_at:
                ns.ministry_published_at = _utcnow()
                counts["published"] += 1

            for unit in subj["units"]:
                nu = (
                    s.query(NationalUnit)
                    .filter(
                        NationalUnit.national_subject_id == ns.id,
                        NationalUnit.code == unit["code"],
                    )
                    .first()
                )
                if nu:
                    counts["units_skipped"] += 1
                else:
                    nu = NationalUnit(
                        id=uuid.uuid4(),
                        national_subject_id=ns.id,
                        name=unit["name"],
                        code=unit["code"],
                        sequence_order=unit["sequence_order"],
                        grade_level=unit.get("grade_level"),
                    )
                    s.add(nu)
                    s.flush()
                    counts["units_created"] += 1

                for topic in unit["topics"]:
                    nt = (
                        s.query(NationalTopic)
                        .filter(
                            NationalTopic.national_unit_id == nu.id,
                            NationalTopic.code == topic["code"],
                        )
                        .first()
                    )
                    if nt:
                        counts["topics_skipped"] += 1
                    else:
                        nt = NationalTopic(
                            id=uuid.uuid4(),
                            national_unit_id=nu.id,
                            name=topic["name"],
                            code=topic["code"],
                            sequence_order=topic["sequence_order"],
                            learning_outcomes=topic.get("learning_outcomes"),
                        )
                        s.add(nt)
                        counts["topics_created"] += 1

        if dry_run:
            s.rollback()
        else:
            s.commit()

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--db-url", default=None,
                        help="DATABASE_URL override")
    parser.add_argument("--no-publish", action="store_true",
                        help="Insert subjects but do not mark as "
                             "published. Schools won't see them until "
                             "an operator publishes via the UI.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be inserted; no commit.")
    args = parser.parse_args()

    counts = seed(
        database_url=args.db_url,
        publish=not args.no_publish,
        dry_run=args.dry_run,
    )
    print()
    print("=" * 60)
    print("EduZim ZIMSEC sample data import — completed")
    print("=" * 60)
    print(f"  Subjects created:   {counts['subjects_created']}")
    print(f"  Subjects skipped:   {counts['subjects_skipped']}  (already existed)")
    print(f"  Units created:      {counts['units_created']}")
    print(f"  Units skipped:      {counts['units_skipped']}")
    print(f"  Topics created:     {counts['topics_created']}")
    print(f"  Topics skipped:     {counts['topics_skipped']}")
    print(f"  Subjects published: {counts['published']}")
    print()
    if args.dry_run:
        print("⚠️  --dry-run set; nothing was actually committed.")
    print()
    print("Sample subjects available for adoption:")
    for subj in SAMPLE:
        print(f"  - {subj['code']}: {subj['name']}")
    print()
    print(
        "⚠️  REMINDER: this is placeholder data. Run "
        "POST /ministry/bulk/national-curriculum with the real ZIMSEC "
        "Excel workbook before any school adopts these subjects in "
        "production."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
