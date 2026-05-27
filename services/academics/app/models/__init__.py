"""academics models package.

PH2-6: school models moved in.
PH2-7: student / parent / enrollment models moved in.
PH2-8: attendance / sync-batch / processed-event models moved in.
PH2-9: assessment / mark / idempotency models moved in. All four academic
       domains now live in academics_db.
"""
from app.models.school import (
    Province,
    District,
    School,
    AcademicYear,
    Term,
    Class,
    Subject,
    ClassTeacherAssignment,
)
from app.models.student import (
    Student,
    Parent,
    StudentParent,
    Enrollment,
    StudentStatus,
    Gender,
    RelationshipType,
    EnrollmentStatus,
)
from app.models.attendance import (
    AttendanceRecord,
    SyncBatch,
    ProcessedClientEvent,
)
from app.models.assessment import (
    Assessment,
    Mark,
)
from app.models.idempotency import IdempotencyKey
from app.models.audit import AuditLog  # Phase 9 / INFRA-018
from app.models.comment_bank import CommentBankPhrase  # Phase 11c / T-007
from app.models.planning import (  # Phase 11d
    SchoolPeriod,
    LessonPlan,
    FormativeAssessment,
    FormativeResponse,
    ExamSeatPlan,
)
from app.models.student_life import (  # Phase 11e
    BehaviorIncident,
    SubstituteGrant,
    Homework,
    HomeworkSubmission,
)
from app.models.org import (  # Phase 11f
    HeadOfDepartmentAssignment,
    CpdRecord,
    SelfEvaluationForm,
)
from app.models.parent_life import (  # Phase 12d/e/f
    SchoolEvent,
    SchoolPerformanceOptOut,
    ConferenceSlot,
    ConferenceBooking,
    PermissionSlip,
    PermissionSlipResponse,
    Grievance,
    TransportBus,
    TransportPing,
    MealCreditAccount,
    Donation,
    NewsletterPost,
    GalleryPhoto,
    SiblingDiscountRule,
)

__all__ = [
    # School (PH2-6)
    "Province",
    "District",
    "School",
    "AcademicYear",
    "Term",
    "Class",
    "Subject",
    "ClassTeacherAssignment",
    # Student (PH2-7)
    "Student",
    "Parent",
    "StudentParent",
    "Enrollment",
    "StudentStatus",
    "Gender",
    "RelationshipType",
    "EnrollmentStatus",
    # Attendance (PH2-8)
    "AttendanceRecord",
    "SyncBatch",
    "ProcessedClientEvent",
    # Assessment (PH2-9)
    "Assessment",
    "Mark",
    "IdempotencyKey",
    # Phase 9 / INFRA-018
    "AuditLog",
    # Phase 11c / T-007
    "CommentBankPhrase",
    # Phase 11d
    "SchoolPeriod",
    "LessonPlan",
    "FormativeAssessment",
    "FormativeResponse",
    "ExamSeatPlan",
    # Phase 11e
    "BehaviorIncident",
    "SubstituteGrant",
    "Homework",
    "HomeworkSubmission",
    # Phase 11f
    "HeadOfDepartmentAssignment",
    "CpdRecord",
    "SelfEvaluationForm",
    # Phase 12d/e/f
    "SchoolEvent",
    "SchoolPerformanceOptOut",
    "ConferenceSlot",
    "ConferenceBooking",
    "PermissionSlip",
    "PermissionSlipResponse",
    "Grievance",
    "TransportBus",
    "TransportPing",
    "MealCreditAccount",
    "Donation",
    "NewsletterPost",
    "GalleryPhoto",
    "SiblingDiscountRule",
]
