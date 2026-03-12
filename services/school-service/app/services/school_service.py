"""
School Service Business Logic
===============================
All validation, constraints, and data operations.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.school import (
    School, AcademicYear, Term, Class, Subject, ClassTeacherAssignment,
)


class SchoolService:
    """School service with strict validation constraints."""

    def __init__(self, db: Session):
        self.db = db

    # ───────────── School ─────────────

    def create_school(self, school_id: uuid.UUID, name: str, country: str = "ZW",
                      tz: str = "Africa/Harare") -> dict:
        school = School(id=school_id, name=name, country=country, timezone=tz)
        self.db.add(school)
        self.db.commit()
        self.db.refresh(school)
        return self._ser_school(school)

    def get_school(self, school_id: uuid.UUID) -> Optional[dict]:
        s = self.db.query(School).filter(School.id == school_id).first()
        return self._ser_school(s) if s else None

    def upsert_school(self, school_id: uuid.UUID, name: str, country: str = "ZW",
                      tz: str = "Africa/Harare") -> dict:
        s = self.db.query(School).filter(School.id == school_id).first()
        if s:
            s.name = name
            s.country = country
            s.timezone = tz
        else:
            s = School(id=school_id, name=name, country=country, timezone=tz)
            self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return self._ser_school(s)

    # ───────────── Academic Year ─────────────

    def create_academic_year(self, school_id: uuid.UUID, name: str,
                              start_date: date, end_date: date, is_active: bool = False) -> dict:
        # Validate dates
        if start_date >= end_date:
            return {"error": "INVALID_DATES", "message": "start_date must be before end_date"}

        # Check overlapping years
        overlap = self.db.query(AcademicYear).filter(
            AcademicYear.school_id == school_id,
            AcademicYear.start_date < end_date,
            AcademicYear.end_date > start_date,
        ).first()
        if overlap:
            return {"error": "OVERLAP", "message": f"Overlaps with academic year '{overlap.name}'"}

        # If is_active, deactivate others
        if is_active:
            self.db.query(AcademicYear).filter(
                AcademicYear.school_id == school_id,
                AcademicYear.is_active == True,
            ).update({"is_active": False})

        ay = AcademicYear(school_id=school_id, name=name,
                          start_date=start_date, end_date=end_date, is_active=is_active)
        self.db.add(ay)
        self.db.commit()
        self.db.refresh(ay)
        return self._ser_year(ay)

    def list_academic_years(self, school_id: uuid.UUID) -> list[dict]:
        years = self.db.query(AcademicYear).filter(
            AcademicYear.school_id == school_id
        ).order_by(AcademicYear.start_date.desc()).all()
        return [self._ser_year(y) for y in years]

    def update_academic_year(self, year_id: uuid.UUID, school_id: uuid.UUID,
                              name: str = None, start_date: date = None,
                              end_date: date = None, is_active: bool = None) -> Optional[dict]:
        ay = self.db.query(AcademicYear).filter(
            AcademicYear.id == year_id,
            AcademicYear.school_id == school_id,
        ).first()
        if not ay:
            return None

        new_start = start_date or ay.start_date
        new_end = end_date or ay.end_date

        if new_start >= new_end:
            return {"error": "INVALID_DATES", "message": "start_date must be before end_date"}

        # Check overlap with other years (exclude self)
        overlap = self.db.query(AcademicYear).filter(
            AcademicYear.school_id == school_id,
            AcademicYear.id != year_id,
            AcademicYear.start_date < new_end,
            AcademicYear.end_date > new_start,
        ).first()
        if overlap:
            return {"error": "OVERLAP", "message": f"Overlaps with '{overlap.name}'"}

        if name is not None:
            ay.name = name
        if start_date is not None:
            ay.start_date = start_date
        if end_date is not None:
            ay.end_date = end_date
        if is_active is not None:
            if is_active:
                self.db.query(AcademicYear).filter(
                    AcademicYear.school_id == school_id,
                    AcademicYear.id != year_id,
                    AcademicYear.is_active == True,
                ).update({"is_active": False})
            ay.is_active = is_active

        self.db.commit()
        self.db.refresh(ay)
        return self._ser_year(ay)

    # ───────────── Term ─────────────

    def create_term(self, school_id: uuid.UUID, academic_year_id: uuid.UUID,
                    name: str, start_date: date, end_date: date,
                    is_active: bool = False) -> dict:
        ay = self.db.query(AcademicYear).filter(
            AcademicYear.id == academic_year_id,
            AcademicYear.school_id == school_id,
        ).first()
        if not ay:
            return {"error": "NOT_FOUND", "message": "Academic year not found"}

        if start_date >= end_date:
            return {"error": "INVALID_DATES", "message": "start_date must be before end_date"}

        # Term dates must fall within academic year
        if start_date < ay.start_date or end_date > ay.end_date:
            return {"error": "OUTSIDE_YEAR", "message": "Term dates must fall within academic year range"}

        # Check overlapping terms within this year
        overlap = self.db.query(Term).filter(
            Term.school_id == school_id,
            Term.academic_year_id == academic_year_id,
            Term.start_date < end_date,
            Term.end_date > start_date,
        ).first()
        if overlap:
            return {"error": "OVERLAP", "message": f"Overlaps with term '{overlap.name}'"}

        # If is_active, deactivate other terms in this year
        if is_active:
            self.db.query(Term).filter(
                Term.school_id == school_id,
                Term.academic_year_id == academic_year_id,
                Term.is_active == True,
            ).update({"is_active": False})

        term = Term(school_id=school_id, academic_year_id=academic_year_id,
                    name=name, start_date=start_date, end_date=end_date, is_active=is_active)
        self.db.add(term)
        self.db.commit()
        self.db.refresh(term)
        return self._ser_term(term)

    def list_terms(self, school_id: uuid.UUID,
                   academic_year_id: uuid.UUID = None) -> list[dict]:
        q = self.db.query(Term).filter(Term.school_id == school_id)
        if academic_year_id:
            q = q.filter(Term.academic_year_id == academic_year_id)
        return [self._ser_term(t) for t in q.order_by(Term.start_date).all()]

    def update_term(self, term_id: uuid.UUID, school_id: uuid.UUID,
                    name: str = None, start_date: date = None,
                    end_date: date = None, is_active: bool = None) -> Optional[dict]:
        term = self.db.query(Term).filter(
            Term.id == term_id, Term.school_id == school_id,
        ).first()
        if not term:
            return None

        ay = self.db.query(AcademicYear).filter(AcademicYear.id == term.academic_year_id).first()
        new_start = start_date or term.start_date
        new_end = end_date or term.end_date

        if new_start >= new_end:
            return {"error": "INVALID_DATES", "message": "start_date must be before end_date"}
        if new_start < ay.start_date or new_end > ay.end_date:
            return {"error": "OUTSIDE_YEAR", "message": "Term dates must fall within academic year range"}

        # Check overlap with other terms (exclude self)
        overlap = self.db.query(Term).filter(
            Term.school_id == school_id,
            Term.academic_year_id == term.academic_year_id,
            Term.id != term_id,
            Term.start_date < new_end,
            Term.end_date > new_start,
        ).first()
        if overlap:
            return {"error": "OVERLAP", "message": f"Overlaps with '{overlap.name}'"}

        if name is not None:
            term.name = name
        if start_date is not None:
            term.start_date = start_date
        if end_date is not None:
            term.end_date = end_date
        if is_active is not None:
            if is_active:
                self.db.query(Term).filter(
                    Term.school_id == school_id,
                    Term.academic_year_id == term.academic_year_id,
                    Term.id != term_id,
                    Term.is_active == True,
                ).update({"is_active": False})
            term.is_active = is_active

        self.db.commit()
        self.db.refresh(term)
        return self._ser_term(term)

    # ───────────── Class ─────────────

    def create_class(self, school_id: uuid.UUID, name: str,
                     section: str = "A", capacity: int = None) -> dict:
        existing = self.db.query(Class).filter(
            Class.school_id == school_id,
            Class.name == name,
            Class.section == section,
        ).first()
        if existing:
            return {"error": "DUPLICATE_CLASS",
                    "message": f"Class '{name}' section '{section}' already exists"}

        cls = Class(school_id=school_id, name=name, section=section, capacity=capacity)
        self.db.add(cls)
        self.db.commit()
        self.db.refresh(cls)
        return self._ser_class(cls)

    def list_classes(self, school_id: uuid.UUID, page: int = 1,
                     page_size: int = 50) -> tuple[list[dict], int]:
        q = self.db.query(Class).filter(
            Class.school_id == school_id, Class.is_active == True,
        )
        total = q.count()
        classes = q.order_by(Class.name, Class.section).offset(
            (page - 1) * page_size).limit(page_size).all()
        return [self._ser_class(c) for c in classes], total

    def update_class(self, class_id: uuid.UUID, school_id: uuid.UUID,
                     name: str = None, section: str = None,
                     capacity: int = None) -> Optional[dict]:
        cls = self.db.query(Class).filter(
            Class.id == class_id, Class.school_id == school_id,
        ).first()
        if not cls:
            return None

        new_name = name or cls.name
        new_section = section or cls.section

        # Check duplicate (exclude self)
        if name or section:
            dup = self.db.query(Class).filter(
                Class.school_id == school_id,
                Class.name == new_name,
                Class.section == new_section,
                Class.id != class_id,
            ).first()
            if dup:
                return {"error": "DUPLICATE_CLASS",
                        "message": f"Class '{new_name}' section '{new_section}' already exists"}

        if name is not None:
            cls.name = name
        if section is not None:
            cls.section = section
        if capacity is not None:
            cls.capacity = capacity

        self.db.commit()
        self.db.refresh(cls)
        return self._ser_class(cls)

    def soft_delete_class(self, class_id: uuid.UUID, school_id: uuid.UUID) -> Optional[dict]:
        cls = self.db.query(Class).filter(
            Class.id == class_id, Class.school_id == school_id,
        ).first()
        if not cls:
            return None
        cls.is_active = False
        self.db.commit()
        self.db.refresh(cls)
        return self._ser_class(cls)

    # ───────────── Subject ─────────────

    def create_subject(self, school_id: uuid.UUID, name: str, code: str) -> dict:
        existing = self.db.query(Subject).filter(
            Subject.school_id == school_id,
            Subject.code == code,
        ).first()
        if existing:
            return {"error": "DUPLICATE_CODE",
                    "message": f"Subject code '{code}' already exists"}

        subj = Subject(school_id=school_id, name=name, code=code)
        self.db.add(subj)
        self.db.commit()
        self.db.refresh(subj)
        return self._ser_subject(subj)

    def list_subjects(self, school_id: uuid.UUID) -> list[dict]:
        subjects = self.db.query(Subject).filter(
            Subject.school_id == school_id, Subject.is_active == True,
        ).order_by(Subject.name).all()
        return [self._ser_subject(s) for s in subjects]

    def update_subject(self, subj_id: uuid.UUID, school_id: uuid.UUID,
                       name: str = None, code: str = None) -> Optional[dict]:
        subj = self.db.query(Subject).filter(
            Subject.id == subj_id, Subject.school_id == school_id,
        ).first()
        if not subj:
            return None

        if code is not None:
            dup = self.db.query(Subject).filter(
                Subject.school_id == school_id,
                Subject.code == code,
                Subject.id != subj_id,
            ).first()
            if dup:
                return {"error": "DUPLICATE_CODE",
                        "message": f"Subject code '{code}' already exists"}
            subj.code = code
        if name is not None:
            subj.name = name

        self.db.commit()
        self.db.refresh(subj)
        return self._ser_subject(subj)

    def soft_delete_subject(self, subj_id: uuid.UUID, school_id: uuid.UUID) -> Optional[dict]:
        subj = self.db.query(Subject).filter(
            Subject.id == subj_id, Subject.school_id == school_id,
        ).first()
        if not subj:
            return None
        subj.is_active = False
        self.db.commit()
        return self._ser_subject(subj)

    # ───────────── Teacher-Class Assignment ─────────────

    def assign_class_teacher(self, school_id: uuid.UUID, class_id: uuid.UUID,
                              teacher_user_id: uuid.UUID,
                              academic_year_id: uuid.UUID) -> dict:
        # Check class belongs to school
        cls = self.db.query(Class).filter(
            Class.id == class_id, Class.school_id == school_id,
        ).first()
        if not cls:
            return {"error": "NOT_FOUND", "message": "Class not found in this school"}

        # Check academic year belongs to school
        ay = self.db.query(AcademicYear).filter(
            AcademicYear.id == academic_year_id, AcademicYear.school_id == school_id,
        ).first()
        if not ay:
            return {"error": "NOT_FOUND", "message": "Academic year not found in this school"}

        # Check one teacher per class per year
        existing = self.db.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.school_id == school_id,
            ClassTeacherAssignment.class_id == class_id,
            ClassTeacherAssignment.academic_year_id == academic_year_id,
        ).first()
        if existing:
            return {"error": "DUPLICATE_ASSIGNMENT",
                    "message": "A teacher is already assigned to this class for this academic year"}

        assignment = ClassTeacherAssignment(
            school_id=school_id,
            class_id=class_id,
            teacher_user_id=teacher_user_id,
            academic_year_id=academic_year_id,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return self._ser_assignment(assignment)

    def list_class_teachers(self, school_id: uuid.UUID,
                             academic_year_id: uuid.UUID = None) -> list[dict]:
        q = self.db.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.school_id == school_id,
        )
        if academic_year_id:
            q = q.filter(ClassTeacherAssignment.academic_year_id == academic_year_id)
        return [self._ser_assignment(a) for a in q.all()]

    def delete_class_teacher(self, assignment_id: uuid.UUID,
                              school_id: uuid.UUID) -> bool:
        a = self.db.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.id == assignment_id,
            ClassTeacherAssignment.school_id == school_id,
        ).first()
        if not a:
            return False
        self.db.delete(a)
        self.db.commit()
        return True

    def is_teacher_authorized_for_class(self, teacher_user_id: uuid.UUID,
                                        class_id: uuid.UUID,
                                        school_id: uuid.UUID) -> bool:
        """Check if a teacher is assigned to a specific class in this school."""
        assignment = self.db.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.teacher_user_id == teacher_user_id,
            ClassTeacherAssignment.class_id == class_id,
            ClassTeacherAssignment.school_id == school_id,
        ).first()
        return assignment is not None

    def is_teacher_authorized_for_student(self, teacher_user_id: uuid.UUID,
                                          student_id: uuid.UUID,
                                          school_id: uuid.UUID,
                                          class_id: uuid.UUID) -> bool:
        """Check if a teacher is assigned to the class the student is enrolled in.

        The caller provides class_id (from enrollment data). This method verifies
        the teacher is assigned to that class in this school.
        """
        return self.is_teacher_authorized_for_class(teacher_user_id, class_id, school_id)

    def get_teacher_class_ids(self, teacher_user_id: uuid.UUID,
                              school_id: uuid.UUID) -> list[uuid.UUID]:
        """Return class IDs assigned to a teacher in this school."""
        assignments = self.db.query(ClassTeacherAssignment).filter(
            ClassTeacherAssignment.teacher_user_id == teacher_user_id,
            ClassTeacherAssignment.school_id == school_id,
        ).all()
        return [a.class_id for a in assignments]

    def get_teacher_classes(self, teacher_user_id: uuid.UUID,
                            school_id: uuid.UUID) -> list[dict]:
        """Return classes assigned to a specific teacher, with class details."""
        assignments = (
            self.db.query(ClassTeacherAssignment)
            .filter(
                ClassTeacherAssignment.teacher_user_id == teacher_user_id,
                ClassTeacherAssignment.school_id == school_id,
            )
            .all()
        )
        results = []
        for a in assignments:
            cls = self.db.query(Class).filter(Class.id == a.class_id).first()
            if cls and cls.is_active:
                d = self._ser_class(cls)
                d["assignment_id"] = str(a.id)
                d["academic_year_id"] = str(a.academic_year_id)
                results.append(d)
        return results

    # ───────────── Serializers ─────────────

    def _ser_school(self, s: School) -> dict:
        return {"id": str(s.id), "name": s.name, "country": s.country,
                "timezone": s.timezone, "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None}

    def _ser_year(self, y: AcademicYear) -> dict:
        return {"id": str(y.id), "school_id": str(y.school_id), "name": y.name,
                "start_date": y.start_date.isoformat(), "end_date": y.end_date.isoformat(),
                "is_active": y.is_active,
                "created_at": y.created_at.isoformat() if y.created_at else None,
                "updated_at": y.updated_at.isoformat() if y.updated_at else None}

    def _ser_term(self, t: Term) -> dict:
        return {"id": str(t.id), "school_id": str(t.school_id),
                "academic_year_id": str(t.academic_year_id), "name": t.name,
                "start_date": t.start_date.isoformat(), "end_date": t.end_date.isoformat(),
                "is_active": t.is_active,
                "created_at": t.created_at.isoformat() if t.created_at else None}

    def _ser_class(self, c: Class) -> dict:
        return {"id": str(c.id), "school_id": str(c.school_id),
                "name": c.name, "section": c.section,
                "capacity": c.capacity, "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None}

    def _ser_subject(self, s: Subject) -> dict:
        return {"id": str(s.id), "school_id": str(s.school_id),
                "name": s.name, "code": s.code, "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None}

    def _ser_assignment(self, a: ClassTeacherAssignment) -> dict:
        return {"id": str(a.id), "school_id": str(a.school_id),
                "class_id": str(a.class_id), "teacher_user_id": str(a.teacher_user_id),
                "academic_year_id": str(a.academic_year_id),
                "created_at": a.created_at.isoformat() if a.created_at else None}
