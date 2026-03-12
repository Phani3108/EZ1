"""
Student Service Business Logic
================================
All validation, constraints, and data operations.
Cross-service validation via SchoolServiceClient.
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.student import (
    Student, Parent, StudentParent, Enrollment,
    StudentStatus, EnrollmentStatus,
)
from app.services.school_client import SchoolServiceClient


class StudentService:
    def __init__(self, db: Session, school_client: SchoolServiceClient = None):
        self.db = db
        self.school_client = school_client

    # ───────────── Students ─────────────

    def create_student(self, school_id: uuid.UUID, student_code: str,
                       first_name: str, last_name: str,
                       dob: date = None, gender: str = None,
                       admission_date: date = None) -> dict:
        existing = self.db.query(Student).filter(
            Student.school_id == school_id,
            Student.student_code == student_code,
        ).first()
        if existing:
            return {"error": "DUPLICATE_CODE",
                    "message": f"Student code '{student_code}' already exists"}

        student = Student(
            school_id=school_id, student_code=student_code,
            first_name=first_name, last_name=last_name,
            dob=dob, gender=gender, admission_date=admission_date,
            status=StudentStatus.ACTIVE.value,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return self._ser_student(student)

    def list_students(self, school_id: uuid.UUID, page: int = 1,
                      page_size: int = 50, status: str = None,
                      query: str = None) -> tuple[list[dict], int]:
        q = self.db.query(Student).filter(
            Student.school_id == school_id,
            Student.deleted_at == None,
        )
        if status:
            q = q.filter(Student.status == status)
        if query:
            q = q.filter(
                (Student.first_name.ilike(f"%{query}%")) |
                (Student.last_name.ilike(f"%{query}%")) |
                (Student.student_code.ilike(f"%{query}%"))
            )
        total = q.count()
        students = q.order_by(Student.last_name, Student.first_name).offset(
            (page - 1) * page_size).limit(page_size).all()
        return [self._ser_student(s) for s in students], total

    def get_student(self, student_id: uuid.UUID,
                    school_id: uuid.UUID) -> Optional[dict]:
        s = self.db.query(Student).filter(
            Student.id == student_id,
            Student.school_id == school_id,
            Student.deleted_at == None,
        ).first()
        return self._ser_student(s) if s else None

    def update_student(self, student_id: uuid.UUID, school_id: uuid.UUID,
                       first_name: str = None, last_name: str = None,
                       dob: date = None, gender: str = None,
                       status: str = None, student_code: str = None) -> Optional[dict]:
        s = self.db.query(Student).filter(
            Student.id == student_id,
            Student.school_id == school_id,
            Student.deleted_at == None,
        ).first()
        if not s:
            return None

        if student_code and student_code != s.student_code:
            dup = self.db.query(Student).filter(
                Student.school_id == school_id,
                Student.student_code == student_code,
                Student.id != student_id,
            ).first()
            if dup:
                return {"error": "DUPLICATE_CODE", "message": f"Student code '{student_code}' already exists"}
            s.student_code = student_code
        if first_name is not None:
            s.first_name = first_name
        if last_name is not None:
            s.last_name = last_name
        if dob is not None:
            s.dob = dob
        if gender is not None:
            s.gender = gender
        if status is not None:
            s.status = status

        self.db.commit()
        self.db.refresh(s)
        return self._ser_student(s)

    def soft_delete_student(self, student_id: uuid.UUID,
                             school_id: uuid.UUID) -> Optional[dict]:
        s = self.db.query(Student).filter(
            Student.id == student_id,
            Student.school_id == school_id,
            Student.deleted_at == None,
        ).first()
        if not s:
            return None

        # Check active enrollments
        active = self.db.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.status == EnrollmentStatus.ENROLLED.value,
        ).first()
        if active:
            return {"error": "ACTIVE_ENROLLMENT",
                    "message": "Cannot delete student with active enrollment"}

        s.deleted_at = datetime.now(timezone.utc)
        s.status = StudentStatus.INACTIVE.value
        self.db.commit()
        self.db.refresh(s)
        return self._ser_student(s)

    # ───────────── Parents ─────────────

    def create_parent(self, school_id: uuid.UUID, first_name: str, last_name: str,
                      phone: str, email: str = None,
                      relationship_type: str = "GUARDIAN") -> dict:
        existing = self.db.query(Parent).filter(
            Parent.school_id == school_id,
            Parent.phone == phone,
        ).first()
        if existing:
            return {"error": "DUPLICATE_PHONE",
                    "message": f"Parent with phone '{phone}' already exists"}

        parent = Parent(
            school_id=school_id, first_name=first_name, last_name=last_name,
            phone=phone, email=email, relationship_type=relationship_type,
        )
        self.db.add(parent)
        self.db.commit()
        self.db.refresh(parent)
        return self._ser_parent(parent)

    def list_parents(self, school_id: uuid.UUID) -> list[dict]:
        parents = self.db.query(Parent).filter(Parent.school_id == school_id).all()
        return [self._ser_parent(p) for p in parents]

    def update_parent(self, parent_id: uuid.UUID, school_id: uuid.UUID,
                      first_name: str = None, last_name: str = None,
                      phone: str = None, email: str = None) -> Optional[dict]:
        p = self.db.query(Parent).filter(
            Parent.id == parent_id, Parent.school_id == school_id,
        ).first()
        if not p:
            return None
        if phone and phone != p.phone:
            dup = self.db.query(Parent).filter(
                Parent.school_id == school_id,
                Parent.phone == phone,
                Parent.id != parent_id,
            ).first()
            if dup:
                return {"error": "DUPLICATE_PHONE", "message": f"Phone '{phone}' already taken"}
            p.phone = phone
        if first_name is not None:
            p.first_name = first_name
        if last_name is not None:
            p.last_name = last_name
        if email is not None:
            p.email = email
        self.db.commit()
        self.db.refresh(p)
        return self._ser_parent(p)

    # ───────────── Parent Linking ─────────────

    def link_parent(self, school_id: uuid.UUID, student_id: uuid.UUID,
                    parent_id: uuid.UUID, is_primary: bool = False) -> dict:
        # Verify both belong to same school
        student = self.db.query(Student).filter(
            Student.id == student_id, Student.school_id == school_id,
            Student.deleted_at == None,
        ).first()
        if not student:
            return {"error": "NOT_FOUND", "message": "Student not found"}

        parent = self.db.query(Parent).filter(
            Parent.id == parent_id, Parent.school_id == school_id,
        ).first()
        if not parent:
            return {"error": "NOT_FOUND", "message": "Parent not found in this school"}

        # Check duplicate link
        existing = self.db.query(StudentParent).filter(
            StudentParent.student_id == student_id,
            StudentParent.parent_id == parent_id,
        ).first()
        if existing:
            return {"error": "DUPLICATE_LINK", "message": "Parent already linked to this student"}

        # If primary, clear other primaries for this student
        if is_primary:
            self.db.query(StudentParent).filter(
                StudentParent.student_id == student_id,
                StudentParent.is_primary == True,
            ).update({"is_primary": False})

        link = StudentParent(
            school_id=school_id, student_id=student_id,
            parent_id=parent_id, is_primary=is_primary,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return self._ser_link(link)

    def get_student_parents(self, student_id: uuid.UUID,
                             school_id: uuid.UUID) -> list[dict]:
        links = self.db.query(StudentParent).filter(
            StudentParent.student_id == student_id,
            StudentParent.school_id == school_id,
        ).all()
        return [self._ser_link(l) for l in links]

    def get_children_by_user_id(self, user_id: uuid.UUID,
                                 school_id: uuid.UUID) -> Optional[list[dict]]:
        """Find the Parent record matching this auth user_id, then return their linked children."""
        parent = self.db.query(Parent).filter(
            Parent.user_id == user_id,
            Parent.school_id == school_id,
        ).first()
        if not parent:
            return None

        links = self.db.query(StudentParent).filter(
            StudentParent.parent_id == parent.id,
            StudentParent.school_id == school_id,
        ).all()

        student_ids = [l.student_id for l in links]
        if not student_ids:
            return []

        students = self.db.query(Student).filter(
            Student.id.in_(student_ids),
            Student.deleted_at == None,
        ).order_by(Student.first_name, Student.last_name).all()
        return [self._ser_student(s) for s in students]

    def verify_parent_child_link(self, user_id: uuid.UUID,
                                  student_id: uuid.UUID,
                                  school_id: uuid.UUID) -> bool:
        """Check whether the auth user (parent) is linked to the given student."""
        parent = self.db.query(Parent).filter(
            Parent.user_id == user_id,
            Parent.school_id == school_id,
        ).first()
        if not parent:
            return False
        link = self.db.query(StudentParent).filter(
            StudentParent.parent_id == parent.id,
            StudentParent.student_id == student_id,
            StudentParent.school_id == school_id,
        ).first()
        return link is not None

    # ───────────── Enrollment ─────────────

    def create_enrollment(self, school_id: uuid.UUID, student_id: uuid.UUID,
                          class_id: uuid.UUID, academic_year_id: uuid.UUID,
                          token: str = "") -> dict:
        # Check student exists and is not soft-deleted
        student = self.db.query(Student).filter(
            Student.id == student_id,
            Student.school_id == school_id,
            Student.deleted_at == None,
        ).first()
        if not student:
            return {"error": "NOT_FOUND", "message": "Student not found"}

        if student.status != StudentStatus.ACTIVE.value:
            return {"error": "INACTIVE_STUDENT", "message": "Cannot enroll inactive student"}

        # Service-to-service: validate class
        if self.school_client:
            cls_result = self.school_client.validate_class(class_id, school_id, token)
            if not cls_result:
                return {"error": "INVALID_CLASS",
                        "message": "Class not found or belongs to different school"}

            year_result = self.school_client.validate_academic_year(
                academic_year_id, school_id, token)
            if not year_result:
                return {"error": "INVALID_YEAR",
                        "message": "Academic year not found or belongs to different school"}

        # One enrollment per student per year (regardless of status)
        existing = self.db.query(Enrollment).filter(
            Enrollment.school_id == school_id,
            Enrollment.student_id == student_id,
            Enrollment.academic_year_id == academic_year_id,
        ).first()
        if existing:
            return {"error": "DUPLICATE_ENROLLMENT",
                    "message": "Student already enrolled for this academic year"}

        enrollment = Enrollment(
            school_id=school_id, student_id=student_id,
            class_id=class_id, academic_year_id=academic_year_id,
            status=EnrollmentStatus.ENROLLED.value,
        )
        self.db.add(enrollment)
        self.db.commit()
        self.db.refresh(enrollment)
        return self._ser_enrollment(enrollment)

    def list_enrollments(self, school_id: uuid.UUID,
                         class_id: uuid.UUID = None,
                         academic_year_id: uuid.UUID = None) -> list[dict]:
        q = self.db.query(Enrollment).filter(Enrollment.school_id == school_id)
        if class_id:
            q = q.filter(Enrollment.class_id == class_id)
        if academic_year_id:
            q = q.filter(Enrollment.academic_year_id == academic_year_id)
        return [self._ser_enrollment(e) for e in q.all()]

    def update_enrollment(self, enrollment_id: uuid.UUID, school_id: uuid.UUID,
                          status: str = None, class_id: uuid.UUID = None) -> Optional[dict]:
        e = self.db.query(Enrollment).filter(
            Enrollment.id == enrollment_id,
            Enrollment.school_id == school_id,
        ).first()
        if not e:
            return None

        if status is not None:
            e.status = status
        if class_id is not None:
            # Validate class via school client if available
            if self.school_client:
                cls_result = self.school_client.validate_class(class_id, school_id, "")
                if not cls_result:
                    return {"error": "INVALID_CLASS", "message": "Class not found"}
            e.class_id = class_id

        self.db.commit()
        self.db.refresh(e)
        return self._ser_enrollment(e)

    # ───────────── Serializers ─────────────

    def _ser_student(self, s: Student) -> dict:
        return {
            "id": str(s.id), "school_id": str(s.school_id),
            "student_code": s.student_code,
            "admission_number": s.student_code,  # Alias for frontend
            "first_name": s.first_name, "last_name": s.last_name,
            "dob": s.dob.isoformat() if s.dob else None,
            "gender": s.gender,
            "admission_date": s.admission_date.isoformat() if s.admission_date else None,
            "status": s.status,
            "is_active": s.status == "ACTIVE",  # Boolean for frontend
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "deleted_at": s.deleted_at.isoformat() if s.deleted_at else None,
        }

    def _ser_parent(self, p: Parent) -> dict:
        return {
            "id": str(p.id), "school_id": str(p.school_id),
            "first_name": p.first_name, "last_name": p.last_name,
            "phone": p.phone, "email": p.email,
            "relationship_type": p.relationship_type,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }

    def _ser_link(self, l: StudentParent) -> dict:
        return {
            "id": str(l.id), "school_id": str(l.school_id),
            "student_id": str(l.student_id), "parent_id": str(l.parent_id),
            "is_primary": l.is_primary,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }

    def _ser_enrollment(self, e: Enrollment) -> dict:
        return {
            "id": str(e.id), "school_id": str(e.school_id),
            "student_id": str(e.student_id),
            "class_id": str(e.class_id),
            "academic_year_id": str(e.academic_year_id),
            "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
