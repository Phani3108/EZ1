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
from app.models.staff import (  # Phase 13a
    NonTeachingStaff,
    LeaveRequest,
    EmploymentContract,
    SalarySlip,
    PerformanceReview,
    AdmissionApplication,
    StudentTransfer,
)
from app.models.compliance import (  # Phase 13b
    ComplianceReportTemplate,
    ComplianceReportSubmission,
    HealthRecord,
)
from app.models.ops import (  # Phase 13c
    Expense,
    VendorPayment,
    CapitalProject,
    Asset,
    AssetMovement,
    LibraryBook,
    BookLoan,
    Visitor,
)
from app.models.community import (  # Phase 13d
    PolicyDocument,
    Sponsor,
    Sponsorship,
    Alumnus,
)
from app.models.special import (  # Phase 13e
    BoardingRoom,
    BoardingAssignment,
    Campus,
)
from app.models.onboarding import (  # Phase 15
    StudentDraft,
    ParentDraft,
    InviteRequest,
)
from app.models.curriculum import (  # Phase 16
    Unit,
    Topic,
)
from app.models.national_curriculum import (  # Phase 16
    NationalSubject,
    NationalUnit,
    NationalTopic,
)
from app.models.question_bank import (  # Phase 16c
    Question,
    QuestionOption,
    QuestionDraft,
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
    # Phase 13a
    "NonTeachingStaff",
    "LeaveRequest",
    "EmploymentContract",
    "SalarySlip",
    "PerformanceReview",
    "AdmissionApplication",
    "StudentTransfer",
    # Phase 13b
    "ComplianceReportTemplate",
    "ComplianceReportSubmission",
    "HealthRecord",
    # Phase 13c
    "Expense",
    "VendorPayment",
    "CapitalProject",
    "Asset",
    "AssetMovement",
    "LibraryBook",
    "BookLoan",
    "Visitor",
    # Phase 13d
    "PolicyDocument",
    "Sponsor",
    "Sponsorship",
    "Alumnus",
    # Phase 13e
    "BoardingRoom",
    "BoardingAssignment",
    "Campus",
    # Phase 15
    "StudentDraft",
    "ParentDraft",
    "InviteRequest",
    # Phase 16
    "Unit",
    "Topic",
    "NationalSubject",
    "NationalUnit",
    "NationalTopic",
    "Question",
    "QuestionOption",
    "QuestionDraft",
]
