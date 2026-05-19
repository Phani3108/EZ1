#!/usr/bin/env python3
"""Build the EduZim master mock dataset workbook.

Generates ``scripts/data/eduzim_master.xlsx`` containing every entity needed
to populate the platform end-to-end:

    Provinces, Districts, Schools, AcademicYears, Terms, Subjects, Classes,
    Teachers, Parents, Students, StudentParents, ClassTeacherAssignments,
    Enrollments, FeeStructures, FeeItems, Invoices, Payments,
    Assessments, Marks, Attendance, Announcements.

Determinism
-----------
A fixed ``random.Random(SEED)`` plus sorted iteration order means the workbook
bytes are identical across runs (so ``git diff`` is meaningful and CI can detect
drift between the workbook and the regenerated frontend mock store).

Usage
-----
    python scripts/build_master_dataset.py
    python scripts/build_master_dataset.py --schools-per-province 3   # smaller demo
    python scripts/build_master_dataset.py --out /tmp/eduzim.xlsx
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Allow ``shared/`` import without installing the package
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared"))

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from eduzim_shared.reference import (
    ZIMBABWE_PROVINCES,
    ZIMBABWE_DISTRICTS,
    DISTRICTS_BY_PROVINCE_CODE,
)

SEED = 42
DEFAULT_SCHOOLS_PER_PROVINCE = 6
DEFAULT_STUDENTS_PER_SCHOOL = 80
ATTENDANCE_DAYS_PER_STUDENT = 30
ACADEMIC_YEAR = 2026


# ─── Name pools (Shona / Ndebele / English mix; used by full-seed.py also) ────
SURNAMES = [
    "Moyo", "Ncube", "Sibanda", "Ndlovu", "Dube", "Mpofu", "Banda", "Nyathi",
    "Mhlanga", "Tshuma", "Chigumba", "Chigwedere", "Mutasa", "Mugabe", "Chiweshe",
    "Chinhoyi", "Mudenda", "Mutema", "Ruzvidzo", "Zimuto", "Mandaza", "Makoni",
    "Maguwu", "Mukoma", "Munyaradzi", "Madondo", "Madziva", "Maposa", "Mapfumo",
    "Mhembere", "Chiwenga", "Mawere", "Marufu", "Murambadoro", "Manyika",
    "Chari", "Chitanda", "Gomba", "Kanengoni", "Kapfumvuti", "Maramba",
]
FIRST_NAMES_M = [
    "Tendai", "Tafara", "Tinashe", "Tatenda", "Tonderai", "Tichaona", "Tawanda",
    "Tafadzwa", "Tonderai", "Takudzwa", "Brian", "Brighton", "Blessing", "Caleb",
    "Clive", "Daniel", "Edmore", "Emmanuel", "Farai", "Garikai", "Gift", "Hardlife",
    "Honest", "Innocent", "Itai", "Justice", "Knowledge", "Learnmore", "Liberty",
    "Munashe", "Munyaradzi", "Pardon", "Privilege", "Tinotenda",
]
FIRST_NAMES_F = [
    "Chipo", "Chiedza", "Chiratidzo", "Faith", "Fungai", "Gamuchirai", "Grace",
    "Hazel", "Hope", "Joyce", "Kundai", "Linda", "Mavis", "Mercy", "Memory",
    "Nyasha", "Patience", "Patricia", "Precious", "Privilege", "Rudo", "Ruvimbo",
    "Shamiso", "Shingirai", "Tariro", "Tatenda", "Tendai", "Thandiwe", "Tsitsi",
    "Vimbai",
]
OCCUPATIONS = [
    "Teacher", "Nurse", "Farmer", "Police Officer", "Driver", "Shop Owner",
    "Civil Servant", "Engineer", "Tailor", "Carpenter", "Mechanic", "Vendor",
    "Banker", "Pastor", "Chef", "Accountant", "Electrician", "Plumber",
    "Security Guard", "Receptionist",
]
SCHOOL_NAME_PREFIXES = [
    "St. Mary's", "St. Peter's", "Mufakose", "Nyanga", "Mt. Pleasant",
    "Heritage", "Vision", "Cornerstone", "Murewa", "Goromonzi",
    "Founders", "Pumula", "Mzilikazi", "Kwekwe", "Lupane",
    "Kariba", "Glen View", "Hwange", "Chinhoyi", "Bindura",
    "Marondera", "Chivhu", "Beitbridge", "Chiredzi", "Mutare",
    "Nkayi", "Tsholotsho", "Gwanda", "Plumtree", "Esigodini",
]
SCHOOL_NAME_SUFFIXES = ["Primary School", "Secondary School", "High School", "Academy"]
SUBJECT_CATALOG = [
    ("ENG", "English Language", "Languages"),
    ("SHO", "Shona", "Languages"),
    ("NDE", "Ndebele", "Languages"),
    ("MAT", "Mathematics", "STEM"),
    ("SCI", "Combined Science", "STEM"),
    ("BIO", "Biology", "STEM"),
    ("CHE", "Chemistry", "STEM"),
    ("PHY", "Physics", "STEM"),
    ("HIS", "History", "Humanities"),
    ("GEO", "Geography", "Humanities"),
    ("FRS", "Family & Religious Studies", "Humanities"),
    ("COM", "Computer Studies", "STEM"),
    ("PED", "Physical Education", "Skills"),
]
PAYMENT_METHODS = ["CASH", "EcoCash", "ZIPIT", "OneMoney", "BankTransfer"]
TRANSPORT_MODES = ["Walking", "Bicycle", "Combi", "School Bus", "Car"]
BLOOD_GROUPS = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]


# ─── Helpers ───────────────────────────────────────────────────────────────
def stable_uuid(rng_namespace: str) -> str:
    """Generate a UUID-shaped string deterministically from a namespace."""
    h = hashlib.sha1(rng_namespace.encode("utf-8")).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def gender_pick(rng: random.Random) -> str:
    return "M" if rng.random() < 0.5 else "F"


def pick_first_name(rng: random.Random, gender: str) -> str:
    return rng.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F)


def email_for(first: str, last: str, suffix: str = "@eduzim.zw") -> str:
    return f"{first.lower()}.{last.lower()}{suffix}".replace(" ", "")


def phone_for(rng: random.Random) -> str:
    return f"+26371{rng.randint(1000000, 9999999)}"


# ─── Generation entry point ────────────────────────────────────────────────
@dataclass
class GenConfig:
    schools_per_province: int = DEFAULT_SCHOOLS_PER_PROVINCE
    students_per_school: int = DEFAULT_STUDENTS_PER_SCHOOL
    attendance_days: int = ATTENDANCE_DAYS_PER_STUDENT
    academic_year: int = ACADEMIC_YEAR
    out_path: Path = Path("scripts/data/eduzim_master.xlsx")


def build(cfg: GenConfig) -> Dict[str, List[Dict]]:
    rng = random.Random(SEED)

    data: Dict[str, List[Dict]] = {sheet: [] for sheet in (
        "Provinces", "Districts", "Schools", "AcademicYears", "Terms", "Subjects",
        "Classes", "Teachers", "Parents", "Students", "StudentParents",
        "ClassTeacherAssignments", "Enrollments", "FeeStructures", "FeeItems",
        "Invoices", "Payments", "Assessments", "Marks", "Attendance", "Announcements",
    )}

    # ─── Provinces & Districts ────────────────────────────────────────────
    for p in ZIMBABWE_PROVINCES:
        data["Provinces"].append({
            "id": stable_uuid(f"province:{p.code}"),
            "code": p.code,
            "name": p.name,
            "region": p.region,
            "capital": p.capital,
        })
    for d in ZIMBABWE_DISTRICTS:
        data["Districts"].append({
            "id": stable_uuid(f"district:{d.code}"),
            "code": d.code,
            "name": d.name,
            "province_code": d.province_code,
        })

    # ─── Schools ───────────────────────────────────────────────────────────
    school_idx = 0
    for province in ZIMBABWE_PROVINCES:
        districts = DISTRICTS_BY_PROVINCE_CODE[province.code]
        for i in range(cfg.schools_per_province):
            school_idx += 1
            district = districts[i % len(districts)]
            school_type = rng.choices(["PRIMARY", "SECONDARY"], weights=[0.4, 0.6])[0]
            prefix = SCHOOL_NAME_PREFIXES[(school_idx * 7) % len(SCHOOL_NAME_PREFIXES)]
            suffix = SCHOOL_NAME_SUFFIXES[2 if school_type == "SECONDARY" else 0]
            name = f"{prefix} {suffix}"
            domain_slug = prefix.lower().replace(" ", "").replace(".", "").replace("'", "")
            data["Schools"].append({
                "id": stable_uuid(f"school:{province.code}:{i}"),
                "name": name,
                "code": f"SCH-{province.code}-{i+1:02d}",
                "province_code": province.code,
                "district_code": district.code,
                "type": school_type,
                "address": f"Plot {rng.randint(10, 999)}, {district.name}",
                "phone": phone_for(rng),
                "email": f"info@{domain_slug}.edu.zw",
                "founded_year": rng.randint(1958, 2018),
                "principal_name": f"{pick_first_name(rng, 'M')} {rng.choice(SURNAMES)}",
                "current_enrollment": cfg.students_per_school + rng.randint(-15, 25),
                "is_demo": True,
            })

    # ─── Academic Year & Terms (one per school) ──────────────────────────
    year_label = f"{cfg.academic_year} Academic Year"
    for sch in data["Schools"]:
        ay_id = stable_uuid(f"ay:{sch['id']}")
        data["AcademicYears"].append({
            "id": ay_id,
            "school_id": sch["id"],
            "name": year_label,
            "start_date": date(cfg.academic_year, 1, 10),
            "end_date": date(cfg.academic_year, 12, 5),
            "is_active": True,
        })
        # 3 terms
        term_windows = [
            (date(cfg.academic_year, 1, 10),  date(cfg.academic_year, 4, 12), "Term 1", True),
            (date(cfg.academic_year, 5, 6),   date(cfg.academic_year, 8, 9),  "Term 2", False),
            (date(cfg.academic_year, 9, 9),   date(cfg.academic_year, 12, 5), "Term 3", False),
        ]
        for start, end, label, active in term_windows:
            data["Terms"].append({
                "id": stable_uuid(f"term:{sch['id']}:{label}"),
                "school_id": sch["id"],
                "academic_year_id": ay_id,
                "name": label,
                "start_date": start,
                "end_date": end,
                "is_active": active,
            })

    # ─── Subjects (one row per school × subject — schools share catalog) ─
    for sch in data["Schools"]:
        for code, name, group in SUBJECT_CATALOG:
            data["Subjects"].append({
                "id": stable_uuid(f"subj:{sch['id']}:{code}"),
                "school_id": sch["id"],
                "code": code,
                "name": name,
                "group": group,
                "is_active": True,
            })

    # ─── Classes (8 per school: Form 1A/B, 2A/B, 3A/B, 4A/B) ──────────────
    class_labels = [("Form 1", "A"), ("Form 1", "B"), ("Form 2", "A"), ("Form 2", "B"),
                    ("Form 3", "A"), ("Form 3", "B"), ("Form 4", "A"), ("Form 4", "B")]
    for sch in data["Schools"]:
        for form, section in class_labels:
            data["Classes"].append({
                "id": stable_uuid(f"class:{sch['id']}:{form}:{section}"),
                "school_id": sch["id"],
                "name": form,
                "section": section,
                "capacity": 40,
                "is_active": True,
            })

    # ─── Teachers (~25 per school) ────────────────────────────────────────
    classes_by_school = {sch["id"]: [c for c in data["Classes"] if c["school_id"] == sch["id"]] for sch in data["Schools"]}
    subjects_by_school = {sch["id"]: [s for s in data["Subjects"] if s["school_id"] == sch["id"]] for sch in data["Schools"]}

    for sch in data["Schools"]:
        for i in range(25):
            g = gender_pick(rng)
            first = pick_first_name(rng, g)
            last = rng.choice(SURNAMES)
            tid = stable_uuid(f"teacher:{sch['id']}:{i}")
            primary_subject = rng.choice(SUBJECT_CATALOG)[1]
            data["Teachers"].append({
                "id": tid,
                "school_id": sch["id"],
                "employee_id": f"T-{sch['code']}-{i+1:03d}",
                "first_name": first,
                "last_name": last,
                "gender": g,
                "dob": date(rng.randint(1968, 1995), rng.randint(1, 12), rng.randint(1, 28)),
                "email": email_for(first, last, f".{sch['code'].lower()}@eduzim.zw"),
                "phone": phone_for(rng),
                "hire_date": date(rng.randint(2008, 2024), rng.randint(1, 12), rng.randint(1, 28)),
                "primary_subject": primary_subject,
                "qualifications": rng.choice(["BEd", "BSc + PGDE", "Dip.Ed", "MEd"]),
                "salary_band": rng.choice(["E1", "E2", "E3", "D1", "D2"]),
                "status": "ACTIVE",
            })

    # ─── ClassTeacherAssignments ──────────────────────────────────────────
    teachers_by_school = {sch["id"]: [t for t in data["Teachers"] if t["school_id"] == sch["id"]] for sch in data["Schools"]}
    for sch in data["Schools"]:
        ay = next(a for a in data["AcademicYears"] if a["school_id"] == sch["id"])
        sch_classes = classes_by_school[sch["id"]]
        sch_teachers = teachers_by_school[sch["id"]]
        for idx, cls in enumerate(sch_classes):
            teacher = sch_teachers[idx % len(sch_teachers)]
            data["ClassTeacherAssignments"].append({
                "id": stable_uuid(f"cta:{cls['id']}"),
                "school_id": sch["id"],
                "class_id": cls["id"],
                "teacher_id": teacher["id"],
                "academic_year_id": ay["id"],
            })

    # ─── Students + Parents + StudentParents + Enrollments ───────────────
    for sch in data["Schools"]:
        sch_classes = classes_by_school[sch["id"]]
        ay = next(a for a in data["AcademicYears"] if a["school_id"] == sch["id"])
        province_code = sch["province_code"]
        district_code = sch["district_code"]
        for n in range(cfg.students_per_school):
            g = gender_pick(rng)
            first = pick_first_name(rng, g)
            last = rng.choice(SURNAMES)
            cls = sch_classes[n % len(sch_classes)]
            form_no = int(cls["name"].split()[1])  # 1..4
            birth_year = cfg.academic_year - (10 + form_no) - rng.randint(0, 1)
            sid = stable_uuid(f"student:{sch['id']}:{n}")
            student_code = f"{province_code}-{cfg.academic_year}-{school_idx_lookup(sch, data['Schools']):02d}-{n+1:04d}"
            transport = rng.choices(TRANSPORT_MODES, weights=[0.45, 0.15, 0.20, 0.15, 0.05])[0]
            data["Students"].append({
                "id": sid,
                "school_id": sch["id"],
                "student_code": student_code,
                "first_name": first,
                "last_name": last,
                "gender": g,
                "dob": date(birth_year, rng.randint(1, 12), rng.randint(1, 28)),
                "address": f"House {rng.randint(10, 9999)}, {sch['district_code'].split('-')[-1].title()}",
                "suburb": sch["district_code"],
                "district_code": district_code,
                "province_code": province_code,
                "admission_date": date(cfg.academic_year - (form_no - 1), 1, 15),
                "status": "ACTIVE",
                "blood_group": rng.choice(BLOOD_GROUPS),
                "special_needs": rng.random() < 0.05,
                "transport_mode": transport,
                "distance_km": round(rng.uniform(0.3, 18.0), 1),
            })

            # Enrollment
            data["Enrollments"].append({
                "id": stable_uuid(f"enr:{sid}"),
                "school_id": sch["id"],
                "student_id": sid,
                "class_id": cls["id"],
                "academic_year_id": ay["id"],
                "status": "ENROLLED",
                "enrolled_at": date(cfg.academic_year, 1, 15),
            })

            # 1 or 2 parents per student
            num_parents = rng.choices([1, 2], weights=[0.25, 0.75])[0]
            for p_idx in range(num_parents):
                pg = "M" if p_idx == 0 else "F" if num_parents == 2 else gender_pick(rng)
                pfirst = pick_first_name(rng, pg)
                # Parents often share surname with one child
                plast = last if rng.random() < 0.85 else rng.choice(SURNAMES)
                pid = stable_uuid(f"parent:{sid}:{p_idx}")
                rel = "FATHER" if pg == "M" else "MOTHER"
                data["Parents"].append({
                    "id": pid,
                    "school_id": sch["id"],
                    "first_name": pfirst,
                    "last_name": plast,
                    "gender": pg,
                    "phone": phone_for(rng),
                    "email": email_for(pfirst, plast, "@gmail.com"),
                    "relationship_type": rel,
                    "occupation": rng.choice(OCCUPATIONS),
                    "address": f"House {rng.randint(10, 9999)}, {district_code}",
                })
                data["StudentParents"].append({
                    "id": stable_uuid(f"sp:{sid}:{pid}"),
                    "school_id": sch["id"],
                    "student_id": sid,
                    "parent_id": pid,
                })

    # ─── FeeStructures + FeeItems ─────────────────────────────────────────
    for sch in data["Schools"]:
        ay = next(a for a in data["AcademicYears"] if a["school_id"] == sch["id"])
        terms = [t for t in data["Terms"] if t["school_id"] == sch["id"]]
        base = 350 if sch["type"] == "PRIMARY" else 550
        for term in terms:
            fs_id = stable_uuid(f"fs:{sch['id']}:{term['id']}")
            data["FeeStructures"].append({
                "id": fs_id,
                "school_id": sch["id"],
                "academic_year_id": ay["id"],
                "term_id": term["id"],
                "name": f"{term['name']} Fees",
                "is_active": term["is_active"],
            })
            items = [
                ("Tuition",       base),
                ("Examination",   45),
                ("Sports",        25),
                ("Library",       15),
                ("Building Levy", 30),
            ]
            for label, amt in items:
                data["FeeItems"].append({
                    "id": stable_uuid(f"fi:{fs_id}:{label}"),
                    "fee_structure_id": fs_id,
                    "label": label,
                    "amount": amt,
                    "currency": "USD",
                })

    # ─── Invoices + Payments (only current term) ─────────────────────────
    invoice_due = date(cfg.academic_year, 2, 20)
    for sch in data["Schools"]:
        current_fs = next(
            f for f in data["FeeStructures"]
            if f["school_id"] == sch["id"] and f["is_active"]
        )
        total = sum(i["amount"] for i in data["FeeItems"] if i["fee_structure_id"] == current_fs["id"])
        sch_students = [s for s in data["Students"] if s["school_id"] == sch["id"]]
        for st in sch_students:
            inv_id = stable_uuid(f"inv:{st['id']}:{current_fs['id']}")
            # 60% fully paid, 20% partial, 20% unpaid
            r = rng.random()
            paid = total if r < 0.60 else round(total * rng.uniform(0.2, 0.8), 2) if r < 0.80 else 0
            status = "PAID" if paid >= total else ("PARTIAL" if paid > 0 else "PENDING")
            data["Invoices"].append({
                "id": inv_id,
                "school_id": sch["id"],
                "student_id": st["id"],
                "fee_structure_id": current_fs["id"],
                "total_amount": total,
                "paid_amount": paid,
                "balance": round(total - paid, 2),
                "currency": "USD",
                "due_date": invoice_due,
                "status": status,
                "created_at": date(cfg.academic_year, 1, 15),
            })
            if paid > 0:
                # 1 or 2 payments
                n_pays = 1 if r < 0.50 else 2
                remaining = paid
                for p_n in range(n_pays):
                    amt = remaining if p_n == n_pays - 1 else round(remaining * 0.5, 2)
                    remaining -= amt
                    method = rng.choice(PAYMENT_METHODS)
                    data["Payments"].append({
                        "id": stable_uuid(f"pay:{inv_id}:{p_n}"),
                        "school_id": sch["id"],
                        "invoice_id": inv_id,
                        "amount": amt,
                        "currency": "USD",
                        "method": method,
                        "reference": f"{method.upper()[:3]}-{rng.randint(10000, 99999)}",
                        "paid_at": date(cfg.academic_year, 1, rng.randint(20, 28)) + timedelta(days=p_n * 5),
                    })

    # ─── Assessments + Marks ─────────────────────────────────────────────
    assessment_types = ["QUIZ", "TEST", "EXAM"]
    for sch in data["Schools"]:
        ay = next(a for a in data["AcademicYears"] if a["school_id"] == sch["id"])
        terms = [t for t in data["Terms"] if t["school_id"] == sch["id"]]
        sch_subjects = subjects_by_school[sch["id"]]
        sch_classes = classes_by_school[sch["id"]]
        sch_teachers = teachers_by_school[sch["id"]]
        for cls in sch_classes:
            # 6 assessments per class (mix of subjects)
            chosen_subjects = rng.sample(sch_subjects, 6)
            for s_idx, subj in enumerate(chosen_subjects):
                term = terms[s_idx % 3]
                a_type = assessment_types[s_idx % len(assessment_types)]
                a_id = stable_uuid(f"asmt:{cls['id']}:{subj['id']}:{s_idx}")
                a_date = term["start_date"] + timedelta(days=15 + s_idx * 4)
                created_by = sch_teachers[s_idx % len(sch_teachers)]
                data["Assessments"].append({
                    "id": a_id,
                    "school_id": sch["id"],
                    "academic_year_id": ay["id"],
                    "term_id": term["id"],
                    "class_id": cls["id"],
                    "subject_id": subj["id"],
                    "subject_code": subj["code"],
                    "subject_name": subj["name"],
                    "name": f"{subj['code']} {a_type.title()} {s_idx + 1}",
                    "type": a_type,
                    "date": a_date,
                    "max_marks": 100,
                    "created_by": created_by["id"],
                })
                cls_students = [
                    s for s in data["Students"] if s["school_id"] == sch["id"]
                    and next((e for e in data["Enrollments"] if e["student_id"] == s["id"]), {}).get("class_id") == cls["id"]
                ]
                for st in cls_students:
                    # ability score derived from student id hash → stable bell-ish curve
                    bias = (int(hashlib.md5(st["id"].encode()).hexdigest(), 16) % 30) + 50  # 50..80
                    marks = max(0, min(100, int(rng.gauss(bias, 12))))
                    is_absent = rng.random() < 0.03
                    data["Marks"].append({
                        "id": stable_uuid(f"mark:{a_id}:{st['id']}"),
                        "school_id": sch["id"],
                        "assessment_id": a_id,
                        "student_id": st["id"],
                        "marks": None if is_absent else marks,
                        "is_absent": is_absent,
                        "remarks": "",
                        "graded_by": created_by["id"],
                        "graded_at": a_date + timedelta(days=2),
                    })

    # ─── Attendance (per-student × N days; P/A/L weighted) ───────────────
    today = date(cfg.academic_year, 2, 14)
    weights = [0.86, 0.08, 0.06]  # Present, Absent, Late
    for sch in data["Schools"]:
        sch_students = [s for s in data["Students"] if s["school_id"] == sch["id"]]
        for st in sch_students:
            enr = next(e for e in data["Enrollments"] if e["student_id"] == st["id"])
            for d_off in range(cfg.attendance_days):
                day = today - timedelta(days=d_off)
                # skip weekends
                if day.weekday() >= 5:
                    continue
                status_char = rng.choices(["P", "A", "L"], weights=weights)[0]
                data["Attendance"].append({
                    "id": stable_uuid(f"att:{st['id']}:{day.isoformat()}"),
                    "school_id": sch["id"],
                    "student_id": st["id"],
                    "class_id": enr["class_id"],
                    "date": day,
                    "status": status_char,
                    "marked_by_user_id": None,
                    "device_id": "MOCK-TABLET-001",
                })

    # ─── Announcements (6 per school) ─────────────────────────────────────
    sample_titles = [
        ("Term Opening Notice", "Welcome back! Lessons resume on Monday."),
        ("Sports Day", "Annual sports day will be held next Friday."),
        ("Parents Meeting", "All parents are invited to the termly meeting."),
        ("Fees Reminder", "Kindly settle all outstanding fees by month-end."),
        ("Library Drive", "Book donations welcome at the school library."),
        ("Vaccination Drive", "Ministry of Health team visits next Tuesday."),
    ]
    for sch in data["Schools"]:
        sch_teachers = teachers_by_school[sch["id"]]
        for idx, (title, body) in enumerate(sample_titles):
            posted_by = sch_teachers[idx % len(sch_teachers)]
            data["Announcements"].append({
                "id": stable_uuid(f"ann:{sch['id']}:{idx}"),
                "school_id": sch["id"],
                "title": title,
                "body": body,
                "audience_type": "ALL",
                "audience_class_id": None,
                "audience_role": None,
                "created_by": posted_by["id"],
                "created_at": datetime(cfg.academic_year, 1, 10 + idx),
            })

    return data


def school_idx_lookup(school: Dict, all_schools: List[Dict]) -> int:
    """1-based school index (deterministic)."""
    for i, s in enumerate(all_schools):
        if s["id"] == school["id"]:
            return i + 1
    return 0


# ─── Workbook writer ───────────────────────────────────────────────────────
SHEET_ORDER = [
    "Provinces", "Districts", "Schools", "AcademicYears", "Terms", "Subjects",
    "Classes", "Teachers", "Parents", "Students", "StudentParents",
    "ClassTeacherAssignments", "Enrollments", "FeeStructures", "FeeItems",
    "Invoices", "Payments", "Assessments", "Marks", "Attendance", "Announcements",
]

HEADER_FILL = PatternFill("solid", fgColor="00843D")  # Zimbabwe green
HEADER_FONT = Font(bold=True, color="FFFFFF")


def write_workbook(data: Dict[str, List[Dict]], cfg: GenConfig) -> Path:
    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name in SHEET_ORDER:
        rows = data[sheet_name]
        ws = wb.create_sheet(sheet_name)
        if not rows:
            ws.append(["(empty)"])
            continue
        cols = list(rows[0].keys())
        ws.append(cols)
        for c_idx, _ in enumerate(cols, start=1):
            cell = ws.cell(row=1, column=c_idx)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="left", vertical="center")
        for r in rows:
            ws.append([r.get(c) for c in cols])
        ws.freeze_panes = "A2"
        for c_idx, col in enumerate(cols, start=1):
            ws.column_dimensions[get_column_letter(c_idx)].width = max(12, min(36, len(col) + 4))

    # _meta sheet
    meta = wb.create_sheet("_meta", 0)
    meta.append(["EduZim Master Dataset"])
    meta["A1"].font = Font(bold=True, size=14, color="00843D")
    meta.append([])
    meta.append(["Generated at (UTC)", datetime.now(timezone.utc).isoformat(timespec="seconds")])
    meta.append(["Seed", SEED])
    meta.append(["Schools per province", cfg.schools_per_province])
    meta.append(["Students per school", cfg.students_per_school])
    meta.append(["Attendance days / student", cfg.attendance_days])
    meta.append(["Academic year", cfg.academic_year])
    meta.append([])
    meta.append(["Sheet", "Row count"])
    meta["A10"].font = Font(bold=True)
    meta["B10"].font = Font(bold=True)
    for sheet_name in SHEET_ORDER:
        meta.append([sheet_name, len(data[sheet_name])])
    meta.column_dimensions["A"].width = 32
    meta.column_dimensions["B"].width = 28

    cfg.out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(cfg.out_path)
    return cfg.out_path


# ─── Integrity checks ─────────────────────────────────────────────────────
def verify(data: Dict[str, List[Dict]]) -> List[str]:
    errors: List[str] = []

    def ids(sheet: str) -> set:
        return {r["id"] for r in data[sheet]}

    province_codes = {p["code"] for p in data["Provinces"]}
    school_ids = ids("Schools")
    student_ids = ids("Students")
    class_ids = ids("Classes")
    teacher_ids = ids("Teachers")
    fs_ids = ids("FeeStructures")
    invoice_ids = ids("Invoices")
    assessment_ids = ids("Assessments")
    ay_ids = ids("AcademicYears")
    term_ids = ids("Terms")

    for d in data["Districts"]:
        if d["province_code"] not in province_codes:
            errors.append(f"District {d['code']} -> unknown province {d['province_code']}")
    for s in data["Schools"]:
        if s["province_code"] not in province_codes:
            errors.append(f"School {s['code']} -> unknown province {s['province_code']}")
    for s in data["Students"]:
        if s["school_id"] not in school_ids:
            errors.append(f"Student {s['student_code']} -> unknown school")
    for sp in data["StudentParents"]:
        if sp["student_id"] not in student_ids:
            errors.append(f"StudentParent -> unknown student {sp['student_id']}")
    for e in data["Enrollments"]:
        if e["student_id"] not in student_ids: errors.append("Enrollment -> unknown student")
        if e["class_id"] not in class_ids: errors.append("Enrollment -> unknown class")
        if e["academic_year_id"] not in ay_ids: errors.append("Enrollment -> unknown academic year")
    for cta in data["ClassTeacherAssignments"]:
        if cta["class_id"] not in class_ids: errors.append("CTA -> unknown class")
        if cta["teacher_id"] not in teacher_ids: errors.append("CTA -> unknown teacher")
    for i in data["Invoices"]:
        if i["student_id"] not in student_ids: errors.append("Invoice -> unknown student")
        if i["fee_structure_id"] not in fs_ids: errors.append("Invoice -> unknown fee_structure")
    for p in data["Payments"]:
        if p["invoice_id"] not in invoice_ids: errors.append("Payment -> unknown invoice")
    for m in data["Marks"]:
        if m["assessment_id"] not in assessment_ids: errors.append("Mark -> unknown assessment")
        if m["student_id"] not in student_ids: errors.append("Mark -> unknown student")
    for a in data["Assessments"]:
        if a["class_id"] not in class_ids: errors.append("Assessment -> unknown class")
        if a["term_id"] not in term_ids: errors.append("Assessment -> unknown term")
    return errors


# ─── CLI ──────────────────────────────────────────────────────────────────
def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Build EduZim master mock dataset.")
    ap.add_argument("--schools-per-province", type=int, default=DEFAULT_SCHOOLS_PER_PROVINCE)
    ap.add_argument("--students-per-school", type=int, default=DEFAULT_STUDENTS_PER_SCHOOL)
    ap.add_argument("--attendance-days", type=int, default=ATTENDANCE_DAYS_PER_STUDENT)
    ap.add_argument("--academic-year", type=int, default=ACADEMIC_YEAR)
    ap.add_argument("--out", type=Path, default=ROOT / "scripts/data/eduzim_master.xlsx")
    args = ap.parse_args(argv)

    cfg = GenConfig(
        schools_per_province=args.schools_per_province,
        students_per_school=args.students_per_school,
        attendance_days=args.attendance_days,
        academic_year=args.academic_year,
        out_path=args.out,
    )
    print(f"⇢ Building dataset (seed={SEED}, schools/province={cfg.schools_per_province}, students/school={cfg.students_per_school}) …")
    data = build(cfg)

    print("⇢ Verifying referential integrity …")
    errors = verify(data)
    if errors:
        for e in errors[:20]:
            print(f"  ✗ {e}")
        if len(errors) > 20:
            print(f"  … and {len(errors) - 20} more")
        return 2

    out = write_workbook(data, cfg)
    size_kb = out.stat().st_size // 1024
    print(f"✓ Wrote {out} ({size_kb} KiB)")
    print(f"✓ Sheets:")
    for s in SHEET_ORDER:
        print(f"    {s:28s} {len(data[s]):>8d}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
