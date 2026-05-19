"""
Assessment Service — Business Logic Layer
============================================
CRUD for assessments, bulk marks upsert, student progress, class performance.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case

from app.models.assessment import Assessment, Mark


class AssessmentService:
    def __init__(self, db: Session):
        self.db = db

    # ───────────── Assessment CRUD ─────────────

    def create_assessment(
        self,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        term_id: uuid.UUID,
        class_id: uuid.UUID,
        subject_id: uuid.UUID,
        name: str,
        assessment_type: str,
        date,
        max_marks: Decimal,
        created_by: uuid.UUID,
    ) -> dict:
        assessment = Assessment(
            school_id=str(school_id),
            academic_year_id=str(academic_year_id),
            term_id=str(term_id),
            class_id=str(class_id),
            subject_id=str(subject_id),
            name=name,
            assessment_type=assessment_type,
            date=date,
            max_marks=max_marks,
            created_by=str(created_by),
        )
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        return self._ser_assessment(assessment)

    def list_assessments(
        self,
        school_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
        subject_id: Optional[uuid.UUID] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 200), 500))
        offset = max(0, int(offset or 0))
        q = self.db.query(Assessment).filter(
            Assessment.school_id == str(school_id),
            Assessment.class_id == str(class_id),
            Assessment.term_id == str(term_id),
            Assessment.deleted_at.is_(None),
        )
        if subject_id:
            q = q.filter(Assessment.subject_id == str(subject_id))
        q = q.order_by(Assessment.date.desc()).offset(offset).limit(limit)
        return [self._ser_assessment(a) for a in q.all()]

    def get_assessment(
        self,
        school_id: uuid.UUID,
        assessment_id: uuid.UUID,
    ) -> Optional[dict]:
        a = self.db.query(Assessment).filter(
            Assessment.id == str(assessment_id),
            Assessment.school_id == str(school_id),
            Assessment.deleted_at.is_(None),
        ).first()
        if not a:
            return None
        result = self._ser_assessment(a)
        # Include marks grid
        marks = self.db.query(Mark).filter(
            Mark.assessment_id == str(assessment_id),
            Mark.school_id == str(school_id),
        ).all()
        result["marks"] = [self._ser_mark(m) for m in marks]
        return result

    # ───────────── Bulk Marks Upsert ─────────────

    def bulk_upsert_marks(
        self,
        school_id: uuid.UUID,
        assessment_id: uuid.UUID,
        marks_data: list[dict],
        graded_by: uuid.UUID,
    ) -> dict:
        """
        Upsert marks for an assessment.
        marks_data: [{student_id, marks, is_absent, remarks?}]
        Returns {accepted, updated, errors[]}.
        """
        # Verify assessment exists and belongs to school
        assessment = self.db.query(Assessment).filter(
            Assessment.id == str(assessment_id),
            Assessment.school_id == str(school_id),
            Assessment.deleted_at.is_(None),
        ).first()
        if not assessment:
            return {"accepted": 0, "updated": 0, "errors": ["Assessment not found"]}

        max_marks = float(assessment.max_marks)

        # Pre-fetch existing marks for this assessment
        existing = {}
        rows = self.db.query(Mark).filter(
            Mark.assessment_id == str(assessment_id),
            Mark.school_id == str(school_id),
        ).all()
        for r in rows:
            existing[r.student_id] = r

        accepted = 0
        updated = 0
        errors = []

        for entry in marks_data:
            student_id = str(entry["student_id"])
            is_absent = entry.get("is_absent", False)
            raw_marks = entry.get("marks")
            remarks = entry.get("remarks")

            # Validation: if absent, marks must be null
            if is_absent:
                raw_marks = None
            elif raw_marks is not None:
                try:
                    mark_val = float(raw_marks)
                except (ValueError, TypeError):
                    errors.append(f"Invalid marks for student {student_id}")
                    continue
                if mark_val < 0 or mark_val > max_marks:
                    errors.append(
                        f"Marks {mark_val} out of range [0, {max_marks}] for student {student_id}"
                    )
                    continue
            else:
                errors.append(f"marks required when not absent for student {student_id}")
                continue

            if student_id in existing:
                # Update
                mark_row = existing[student_id]
                mark_row.marks = raw_marks
                mark_row.is_absent = is_absent
                mark_row.remarks = remarks
                mark_row.graded_by = str(graded_by)
                mark_row.graded_at = datetime.now(timezone.utc)
                updated += 1
            else:
                # Insert
                mark_row = Mark(
                    school_id=str(school_id),
                    assessment_id=str(assessment_id),
                    student_id=student_id,
                    marks=raw_marks,
                    is_absent=is_absent,
                    remarks=remarks,
                    graded_by=str(graded_by),
                )
                self.db.add(mark_row)
                accepted += 1

        self.db.commit()
        return {"accepted": accepted, "updated": updated, "errors": errors}

    # ───────────── Student Marks (grouped by subject) ─────────────

    def student_marks(
        self,
        school_id: uuid.UUID,
        student_id: uuid.UUID,
        term_id: Optional[uuid.UUID] = None,
    ) -> list[dict]:
        """
        Get all marks for a student, grouped by subject.
        Returns [{subject_id, assessments: [{assessment, mark}]}]
        """
        q = (
            self.db.query(Mark, Assessment)
            .join(Assessment, Mark.assessment_id == Assessment.id)
            .filter(
                Mark.student_id == str(student_id),
                Mark.school_id == str(school_id),
                Assessment.deleted_at.is_(None),
            )
        )
        if term_id:
            q = q.filter(Assessment.term_id == str(term_id))

        q = q.order_by(Assessment.subject_id, Assessment.date)

        # Group by subject
        subjects = {}
        for mark, assessment in q.all():
            sid = assessment.subject_id
            if sid not in subjects:
                subjects[sid] = {"subject_id": sid, "assessments": []}
            subjects[sid]["assessments"].append({
                "assessment": self._ser_assessment(assessment),
                "mark": self._ser_mark(mark),
            })

        # Compute subject averages
        result = []
        for sid, data in subjects.items():
            total_marks = 0
            total_max = 0
            graded_count = 0
            for entry in data["assessments"]:
                m = entry["mark"]
                if m["marks"] is not None:
                    total_marks += float(m["marks"])
                    total_max += float(entry["assessment"]["max_marks"])
                    graded_count += 1
            data["average_pct"] = (
                round(total_marks / total_max * 100, 1) if total_max > 0 else None
            )
            data["graded_count"] = graded_count
            result.append(data)

        return result

    # ───────────── Class Performance ─────────────

    def class_performance(
        self,
        school_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: Optional[uuid.UUID] = None,
    ) -> dict:
        """
        Aggregated class performance: per-subject averages, pass rates.
        Returns {subjects: [{subject_id, avg_pct, pass_rate, assessment_count, student_count}]}
        """
        q = (
            self.db.query(
                Assessment.subject_id,
                func.count(func.distinct(Mark.student_id)).label("student_count"),
                func.count(Mark.id).label("mark_count"),
                func.avg(
                    case(
                        (Mark.is_absent == False, Mark.marks),  # noqa: E712
                        else_=None,
                    )
                ).label("avg_marks"),
                func.avg(Assessment.max_marks).label("avg_max"),
            )
            .join(Mark, Mark.assessment_id == Assessment.id)
            .filter(
                Assessment.class_id == str(class_id),
                Assessment.school_id == str(school_id),
                Assessment.deleted_at.is_(None),
            )
        )
        if term_id:
            q = q.filter(Assessment.term_id == str(term_id))

        q = q.group_by(Assessment.subject_id)

        # Also get per-subject assessment counts
        assess_counts = {}
        ac_q = self.db.query(
            Assessment.subject_id,
            func.count(Assessment.id).label("cnt"),
        ).filter(
            Assessment.class_id == str(class_id),
            Assessment.school_id == str(school_id),
            Assessment.deleted_at.is_(None),
        )
        if term_id:
            ac_q = ac_q.filter(Assessment.term_id == str(term_id))
        for row in ac_q.group_by(Assessment.subject_id).all():
            assess_counts[row[0]] = row[1]

        # Calculate per-student pass stats per subject
        # Pass = marks >= 50% of max_marks
        pass_q = (
            self.db.query(
                Assessment.subject_id,
                Mark.student_id,
                func.sum(Mark.marks).label("total_marks"),
                func.sum(Assessment.max_marks).label("total_max"),
            )
            .join(Mark, Mark.assessment_id == Assessment.id)
            .filter(
                Assessment.class_id == str(class_id),
                Assessment.school_id == str(school_id),
                Assessment.deleted_at.is_(None),
                Mark.is_absent == False,  # noqa: E712
                Mark.marks.isnot(None),
            )
        )
        if term_id:
            pass_q = pass_q.filter(Assessment.term_id == str(term_id))
        pass_q = pass_q.group_by(Assessment.subject_id, Mark.student_id)

        # Aggregate pass rates per subject
        subject_pass = {}  # subject_id -> {total_students, passing}
        for row in pass_q.all():
            sid = row[0]
            total_m = float(row[2]) if row[2] else 0
            total_mx = float(row[3]) if row[3] else 0
            if sid not in subject_pass:
                subject_pass[sid] = {"total": 0, "passing": 0}
            subject_pass[sid]["total"] += 1
            if total_mx > 0 and (total_m / total_mx) >= 0.5:
                subject_pass[sid]["passing"] += 1

        subjects = []
        for row in q.all():
            sid = row[0]
            avg_m = float(row[3]) if row[3] is not None else 0
            avg_mx = float(row[4]) if row[4] is not None else 0
            avg_pct = round(avg_m / avg_mx * 100, 1) if avg_mx > 0 else None

            pass_info = subject_pass.get(sid, {"total": 0, "passing": 0})
            pass_rate = (
                round(pass_info["passing"] / pass_info["total"] * 100, 1)
                if pass_info["total"] > 0
                else None
            )

            subjects.append({
                "subject_id": sid,
                "avg_pct": avg_pct,
                "pass_rate": pass_rate,
                "assessment_count": assess_counts.get(sid, 0),
                "student_count": int(row[1]),
            })

        return {"subjects": subjects}

    # ───────────── Serializers ─────────────

    def _ser_assessment(self, a: Assessment) -> dict:
        return {
            "id": a.id,
            "school_id": a.school_id,
            "academic_year_id": a.academic_year_id,
            "term_id": a.term_id,
            "class_id": a.class_id,
            "subject_id": a.subject_id,
            "name": a.name,
            "assessment_type": a.assessment_type,
            "date": a.date.isoformat() if a.date else None,
            "max_marks": float(a.max_marks) if a.max_marks is not None else None,
            "created_by": a.created_by,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }

    def _ser_mark(self, m: Mark) -> dict:
        return {
            "id": m.id,
            "assessment_id": m.assessment_id,
            "student_id": m.student_id,
            "marks": float(m.marks) if m.marks is not None else None,
            "is_absent": m.is_absent,
            "remarks": m.remarks,
            "graded_by": m.graded_by,
            "graded_at": m.graded_at.isoformat() if m.graded_at else None,
        }
