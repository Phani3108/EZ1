#!/usr/bin/env python3
"""
EduZim — Comprehensive Mock Data Seed
======================================
Populates ALL databases with rich, realistic Zimbabwean school data.
Designed to be idempotent (ON CONFLICT DO NOTHING / DO UPDATE).

Usage:  DB_HOST=127.0.0.1 python3 scripts/full-seed.py
"""
import psycopg2
import uuid
import random
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# ─── Config ───
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "user": os.environ.get("DB_USER", "eduzim"),
    "password": os.environ.get("DB_PASS", "eduzim_secret"),
    "port": os.environ.get("DB_PORT", "5432"),
}

SCHOOL_ID     = "11111111-1111-1111-1111-111111111111"
ADMIN_ID      = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ACAD_YEAR_ID  = "22222222-2222-2222-2222-222222222222"
TERM1_ID      = "33333333-3333-3333-3333-333333333333"
TERM2_ID      = "33333333-3333-3333-3333-333333333334"
TERM3_ID      = "33333333-3333-3333-3333-333333333335"
NOW           = datetime.now(timezone.utc)
TODAY         = date.today()

# Zimbabwean names
FIRST_NAMES_M = ["Tatenda", "Takudzwa", "Farai", "Tinashe", "Danai", "Prince", "Blessing", "Tawanda",
                 "Kudakwashe", "Simbarashe", "Tapiwa", "Munashe", "Tendai", "Wellington", "Rutendo"]
FIRST_NAMES_F = ["Rudo", "Sekai", "Nozipho", "Vimbai", "Tariro", "Nyasha", "Rumbidzai", "Chipo",
                 "Londiwe", "Hazvinei", "Tsitsi", "Makanaka", "Yeukai", "Rutendo", "Shamiso"]
LAST_NAMES    = ["Moyo", "Ncube", "Dube", "Nyathi", "Sibanda", "Ndlovu", "Maphosa", "Nkomo",
                 "Chigumba", "Mutasa", "Chamisa", "Mnangagwa", "Tsvangirai", "Muzenda", "Zvobgo",
                 "Mutare", "Chakanyuka", "Chirwa", "Manyika", "Matopos", "Gweru", "Hwange",
                 "Marange", "Chipinge", "Chinaka", "Sigauke", "Muzorewa", "Tekere", "Sithole"]

# ─── Helpers ───

def uid(): return str(uuid.uuid4())

def get_conn(db_name):
    return psycopg2.connect(dbname=db_name, **DB_CONFIG)

def execute(db_name, sql, params=None):
    with get_conn(db_name) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()

def execute_many(db_name, sql, params_list):
    with get_conn(db_name) as conn:
        with conn.cursor() as cur:
            for params in params_list:
                try:
                    cur.execute(sql, params)
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    continue
        conn.commit()

def fetch_all(db_name, sql, params=None):
    with get_conn(db_name) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

def random_name(gender=None):
    if gender == "M":
        return random.choice(FIRST_NAMES_M), random.choice(LAST_NAMES)
    elif gender == "F":
        return random.choice(FIRST_NAMES_F), random.choice(LAST_NAMES)
    else:
        return random.choice(FIRST_NAMES_M + FIRST_NAMES_F), random.choice(LAST_NAMES)

def random_phone():
    return f"+2637{random.randint(1,9)}{random.randint(1000000, 9999999)}"


# ═══════════════════════════════════════════════════════════
#  1. SCHOOL SERVICE — Academics
# ═══════════════════════════════════════════════════════════

def seed_academics():
    print("\n📚 Seeding Academics (school_db)...")

    # Academic Year (already exists, upsert)
    execute("school_db", """
        INSERT INTO academic_years (id, school_id, name, start_date, end_date, is_active, created_at, updated_at)
        VALUES (%s, %s, '2026 Academic Year', '2026-01-15', '2026-12-05', true, %s, %s)
        ON CONFLICT (id) DO UPDATE SET is_active = true, updated_at = EXCLUDED.updated_at
    """, (ACAD_YEAR_ID, SCHOOL_ID, NOW, NOW))
    print("  ✅ Academic Year: 2026")

    # Terms (3 terms for Zimbabwe school calendar)
    terms = [
        (TERM1_ID, "Term 1", "2026-01-15", "2026-04-10", True),
        (TERM2_ID, "Term 2", "2026-05-05", "2026-08-08", False),
        (TERM3_ID, "Term 3", "2026-09-07", "2026-12-05", False),
    ]
    for tid, name, start, end, active in terms:
        execute("school_db", """
            INSERT INTO terms (id, school_id, academic_year_id, name, start_date, end_date, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date, is_active = EXCLUDED.is_active
        """, (tid, SCHOOL_ID, ACAD_YEAR_ID, name, start, end, active, NOW))
    print("  ✅ Terms: 3 (Term 1 active)")

    # Subjects (Zimbabwean curriculum)
    subjects_data = [
        ("English Language", "ENG"), ("Shona", "SHO"), ("Ndebele", "NDE"),
        ("Mathematics", "MAT"), ("General Science", "SCI"), ("Social Studies", "SST"),
        ("Geography", "GEO"), ("History", "HIS"), ("Agriculture", "AGR"),
        ("Physical Education", "PE"), ("Art & Design", "ART"), ("Music", "MUS"),
        ("Computer Science", "CSC"),
    ]
    subject_ids = []
    for name, code in subjects_data:
        sid = uid()
        execute("school_db", """
            INSERT INTO subjects (id, school_id, name, code, is_active, created_at)
            VALUES (%s, %s, %s, %s, true, %s)
            ON CONFLICT (school_id, code) DO NOTHING
        """, (sid, SCHOOL_ID, name, code, NOW))
        subject_ids.append(sid)
    # Fetch actual IDs
    rows = fetch_all("school_db", "SELECT id, code FROM subjects WHERE school_id = %s", (SCHOOL_ID,))
    subject_map = {code: str(sid) for sid, code in rows}
    print(f"  ✅ Subjects: {len(subject_map)}")

    # Classes (already exist, fetch them)
    class_rows = fetch_all("school_db", "SELECT id, name FROM classes WHERE school_id = %s ORDER BY name", (SCHOOL_ID,))
    class_map = {name: str(cid) for cid, name in class_rows}
    print(f"  ✅ Classes: {len(class_map)} (existing)")

    # Class-Teacher Assignments
    teacher_rows = fetch_all("auth_db",
        "SELECT id FROM users WHERE school_id = %s AND email LIKE 'teacher.%%' ORDER BY email", (SCHOOL_ID,))
    teacher_ids = [str(r[0]) for r in teacher_rows]

    assigned = 0
    for i, (class_name, class_id) in enumerate(class_map.items()):
        if i < len(teacher_ids):
            execute("school_db", """
                INSERT INTO class_teacher_assignments (id, school_id, class_id, teacher_user_id, academic_year_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (school_id, class_id, academic_year_id) DO NOTHING
            """, (uid(), SCHOOL_ID, class_id, teacher_ids[i], ACAD_YEAR_ID, NOW))
            assigned += 1
    print(f"  ✅ Teacher Assignments: {assigned}")

    return class_map, subject_map, teacher_ids


# ═══════════════════════════════════════════════════════════
#  2. STUDENT SERVICE — People
# ═══════════════════════════════════════════════════════════

def seed_students(class_map):
    print("\n👥 Seeding Students & Parents (student_db)...")

    # Check existing students
    existing = fetch_all("student_db", "SELECT id, student_code FROM students WHERE school_id = %s", (SCHOOL_ID,))
    existing_codes = {code for _, code in existing}
    existing_ids = [str(sid) for sid, _ in existing]

    # Add more students to reach 100
    class_list = list(class_map.values())
    student_ids = list(existing_ids)
    students_to_insert = []
    needed = max(0, 100 - len(existing_ids))

    for i in range(needed):
        sid = uid()
        code = f"STU2026{len(existing_ids) + i:03d}"
        if code in existing_codes:
            continue
        gender = random.choice(["M", "F"])
        first, last = random_name(gender)
        dob = date(2026 - random.randint(6, 18), random.randint(1, 12), random.randint(1, 28))
        admission = date(2026, 1, random.randint(5, 20))
        students_to_insert.append((sid, SCHOOL_ID, code, first, last, dob, gender, admission, "active", NOW, NOW))
        student_ids.append(sid)

    if students_to_insert:
        with get_conn("student_db") as conn:
            with conn.cursor() as cur:
                for s in students_to_insert:
                    try:
                        cur.execute("""
                            INSERT INTO students (id, school_id, student_code, first_name, last_name, dob, gender, admission_date, status, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (school_id, student_code) DO NOTHING
                        """, s)
                    except Exception:
                        conn.rollback()
            conn.commit()
    print(f"  ✅ Students: {len(student_ids)} total ({needed} new)")

    # Refresh student IDs
    all_students = fetch_all("student_db",
        "SELECT id FROM students WHERE school_id = %s ORDER BY student_code", (SCHOOL_ID,))
    student_ids = [str(r[0]) for r in all_students]

    # Enrollments — enroll all students into classes
    enrolled = 0
    for i, sid in enumerate(student_ids):
        class_id = class_list[i % len(class_list)]
        execute("student_db", """
            INSERT INTO enrollments (id, school_id, student_id, class_id, academic_year_id, enrolled_at, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'active', %s)
            ON CONFLICT (school_id, student_id, academic_year_id) DO NOTHING
        """, (uid(), SCHOOL_ID, sid, class_id, ACAD_YEAR_ID, date(2026, 1, 15), NOW))
        enrolled += 1
    print(f"  ✅ Enrollments: {enrolled}")

    # Parents — check existing
    existing_parents = fetch_all("student_db",
        "SELECT id, phone FROM parents WHERE school_id = %s", (SCHOOL_ID,))
    parent_ids = [str(r[0]) for r in existing_parents]
    existing_phones = {r[1] for r in existing_parents}

    # Add parents if needed (target ~60)
    needed_parents = max(0, 60 - len(parent_ids))
    for i in range(needed_parents):
        pid = uid()
        gender = random.choice(["M", "F"])
        first, last = random_name(gender)
        phone = random_phone()
        while phone in existing_phones:
            phone = random_phone()
        existing_phones.add(phone)
        rel = "Father" if gender == "M" else "Mother"
        execute("student_db", """
            INSERT INTO parents (id, school_id, first_name, last_name, phone, relationship_type, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (school_id, phone) DO NOTHING
        """, (pid, SCHOOL_ID, first, last, phone, rel, NOW))
        parent_ids.append(pid)
    print(f"  ✅ Parents: {len(parent_ids)} total")

    # Refresh parent IDs
    all_parents = fetch_all("student_db",
        "SELECT id FROM parents WHERE school_id = %s", (SCHOOL_ID,))
    parent_ids = [str(r[0]) for r in all_parents]

    # Student-Parent links (each student gets 1-2 parents)
    linked = 0
    for i, sid in enumerate(student_ids):
        # Primary parent
        primary_parent = parent_ids[i % len(parent_ids)]
        execute("student_db", """
            INSERT INTO student_parents (id, school_id, student_id, parent_id, is_primary, created_at)
            VALUES (%s, %s, %s, %s, true, %s)
            ON CONFLICT (student_id, parent_id) DO NOTHING
        """, (uid(), SCHOOL_ID, sid, primary_parent, NOW))
        linked += 1

        # Secondary parent for ~60% of students
        if random.random() < 0.6:
            secondary_parent = parent_ids[(i + 30) % len(parent_ids)]
            if secondary_parent != primary_parent:
                execute("student_db", """
                    INSERT INTO student_parents (id, school_id, student_id, parent_id, is_primary, created_at)
                    VALUES (%s, %s, %s, %s, false, %s)
                    ON CONFLICT (student_id, parent_id) DO NOTHING
                """, (uid(), SCHOOL_ID, sid, secondary_parent, NOW))
                linked += 1
    print(f"  ✅ Student-Parent Links: {linked}")

    return student_ids, parent_ids


# ═══════════════════════════════════════════════════════════
#  3. ATTENDANCE SERVICE — Operations
# ═══════════════════════════════════════════════════════════

def seed_attendance(student_ids, class_map, teacher_ids):
    print("\n📋 Seeding Attendance (attendance_db)...")

    # Get enrollments to know which student is in which class
    enrollment_rows = fetch_all("student_db",
        "SELECT student_id, class_id FROM enrollments WHERE school_id = %s AND status = 'active'", (SCHOOL_ID,))
    student_class = {str(sid): str(cid) for sid, cid in enrollment_rows}

    records = 0
    for day_offset in range(30):
        rdate = TODAY - timedelta(days=day_offset)
        if rdate.weekday() >= 5:  # Skip weekends
            continue
        for sid in student_ids:
            class_id = student_class.get(sid)
            if not class_id:
                continue
            # 85% present, 5% late, 10% absent
            roll = random.random()
            if roll < 0.85:
                status = "P"
            elif roll < 0.90:
                status = "L"
            else:
                status = "A"
            teacher_id = teacher_ids[0] if teacher_ids else ADMIN_ID
            execute("attendance_db", """
                INSERT INTO attendance_records (id, school_id, student_id, class_id, date, status, marked_by_user_id, last_modified_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (school_id, student_id, date) DO NOTHING
            """, (uid(), SCHOOL_ID, sid, class_id, rdate, status, teacher_id, NOW, NOW, NOW))
            records += 1

    print(f"  ✅ Attendance Records: ~{records}")
    return records


# ═══════════════════════════════════════════════════════════
#  4. FEES SERVICE — Financial Operations
# ═══════════════════════════════════════════════════════════

def seed_fees(student_ids):
    print("\n💰 Seeding Fees (fees_db)...")

    # Fee Structures (one per term)
    fee_structures = [
        (uid(), "Term 1 Fees 2026", TERM1_ID, True),
        (uid(), "Term 2 Fees 2026", TERM2_ID, False),
        (uid(), "Term 3 Fees 2026", TERM3_ID, False),
    ]
    for fs_id, name, term_id, active in fee_structures:
        execute("fees_db", """
            INSERT INTO fee_structures (id, school_id, academic_year_id, term_id, name, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (fs_id, SCHOOL_ID, ACAD_YEAR_ID, term_id, name, active, NOW))
    print(f"  ✅ Fee Structures: {len(fee_structures)}")

    # Get the actual structure IDs
    struct_rows = fetch_all("fees_db",
        "SELECT id, name FROM fee_structures WHERE school_id = %s ORDER BY name", (SCHOOL_ID,))
    structure_ids = [str(r[0]) for r in struct_rows]
    active_structure_id = structure_ids[0] if structure_ids else fee_structures[0][0]

    # Fee Items for the active structure
    fee_items = [
        ("Tuition", 250.00),
        ("Development Levy", 50.00),
        ("Sports & Activities", 30.00),
        ("Computer Lab", 25.00),
        ("Exam Fee", 25.00),
        ("Library Fee", 10.00),
        ("Stationery Pack", 15.00),
        ("ZIMSEC Levy", 20.00),
    ]
    total_per_student = sum(amt for _, amt in fee_items)

    for label, amount in fee_items:
        execute("fees_db", """
            INSERT INTO fee_items (id, fee_structure_id, label, amount, currency)
            VALUES (%s, %s, %s, %s, 'USD')
            ON CONFLICT (id) DO NOTHING
        """, (uid(), active_structure_id, label, amount))
    print(f"  ✅ Fee Items: {len(fee_items)} (Total: ${total_per_student}/student)")

    # Invoices for each student (one invoice per active fee structure)
    invoice_ids = []
    total_invoiced = 0
    total_paid_amount = 0

    for sid in student_ids:
        inv_id = uid()
        # 70% fully paid, 20% partially paid, 10% unpaid
        roll = random.random()
        if roll < 0.70:
            paid = total_per_student
            status = "paid"
        elif roll < 0.90:
            paid = round(total_per_student * random.uniform(0.3, 0.8), 2)
            status = "partial"
        else:
            paid = 0
            status = "unpaid"

        due_date = date(2026, 2, 28)
        execute("fees_db", """
            INSERT INTO invoices (id, school_id, student_id, fee_structure_id, total_amount, paid_amount, currency, due_date, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'USD', %s, %s, %s, %s)
            ON CONFLICT (student_id, fee_structure_id) DO UPDATE SET
                paid_amount = EXCLUDED.paid_amount, status = EXCLUDED.status, updated_at = EXCLUDED.updated_at
        """, (inv_id, SCHOOL_ID, sid, active_structure_id, total_per_student, paid, due_date, status, NOW, NOW))
        invoice_ids.append((inv_id, paid))
        total_invoiced += total_per_student
        total_paid_amount += paid

    print(f"  ✅ Invoices: {len(invoice_ids)} (${total_invoiced:,.0f} invoiced, ${total_paid_amount:,.0f} paid)")

    # Refresh invoice IDs (in case of conflict resolution)
    inv_rows = fetch_all("fees_db",
        "SELECT id, paid_amount FROM invoices WHERE school_id = %s", (SCHOOL_ID,))
    real_invoices = [(str(r[0]), float(r[1])) for r in inv_rows]

    # Payments for paid/partial invoices
    payment_count = 0
    for inv_id, paid_amount in real_invoices:
        if paid_amount > 0:
            methods = ["cash", "ecocash", "bank_transfer", "zipit"]
            paid_date = NOW - timedelta(days=random.randint(1, 30))
            execute("fees_db", """
                INSERT INTO payments (id, school_id, invoice_id, amount, currency, method, reference, paid_at, created_at)
                VALUES (%s, %s, %s, %s, 'USD', %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (uid(), SCHOOL_ID, inv_id, paid_amount, random.choice(methods),
                  f"PAY-{random.randint(100000, 999999)}", paid_date, NOW))
            payment_count += 1
    print(f"  ✅ Payments: {payment_count}")

    return total_invoiced, total_paid_amount


# ═══════════════════════════════════════════════════════════
#  5. COMMUNICATION SERVICE
# ═══════════════════════════════════════════════════════════

def seed_communications():
    print("\n📢 Seeding Communications (comms_db)...")

    announcements = [
        ("School Opens for Term 1", "Dear parents and students, we are pleased to announce that school opens on 15 January 2026. Please ensure all students have complete uniforms and stationery.", "all"),
        ("COVID-19 Safety Protocols Update", "In line with Ministry of Health guidelines, all students must wear masks in enclosed spaces. Hand sanitiser stations are available at all entry points.", "all"),
        ("Form 4 Mock Examination Schedule", "Mock examinations for Form 4 will commence on 10 March 2026. Timetables are available from the school office.", "class"),
        ("Sports Day 2026", "Annual Sports Day will be held on 28 February 2026 at the school grounds. All students are encouraged to participate. Parents welcome!", "all"),
        ("Fee Payment Reminder", "This is a reminder that all outstanding fees must be paid by 28 February 2026. Payment can be made via EcoCash, bank transfer, or cash at the school office.", "all"),
        ("Parent-Teacher Conference", "The Term 1 Parent-Teacher Conference is scheduled for 14 March 2026 from 8am to 1pm. All parents are expected to attend.", "all"),
        ("Computer Lab Upgrade", "Our computer lab has been upgraded with 30 new computers. Computer Science practicals will resume next week.", "all"),
        ("Agriculture Field Trip", "Grade 5-7 students will visit Mazowe Citrus Estate on 20 February 2026. Permission slips must be returned by 15 February.", "class"),
        ("Library Book Returns", "All library books borrowed last term must be returned by 31 January 2026. Late returns will incur a fine of $1 per day.", "all"),
        ("ZIMSEC O-Level Registration", "Form 4 students must submit ZIMSEC registration forms and fees by 15 February 2026. See the exam secretary for details.", "class"),
        ("School Feeding Programme", "The school feeding programme will provide lunch for all students starting 20 January. Allergies should be reported to the school nurse.", "all"),
        ("Choir Practice Schedule", "Choir practice will be held every Tuesday and Thursday from 3pm to 4pm. New members welcome!", "all"),
    ]

    ann_ids = []
    class_rows = fetch_all("school_db", "SELECT id FROM classes WHERE school_id = %s LIMIT 5", (SCHOOL_ID,))
    class_ids = [str(r[0]) for r in class_rows]

    for i, (title, body, audience) in enumerate(announcements):
        ann_id = uid()
        class_id = class_ids[i % len(class_ids)] if audience == "class" else None
        created = NOW - timedelta(days=random.randint(0, 25))
        execute("comms_db", """
            INSERT INTO announcements (id, school_id, title, body, audience_type, audience_class_id, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (ann_id, SCHOOL_ID, title, body, audience, class_id, ADMIN_ID, created))
        ann_ids.append(ann_id)

    print(f"  ✅ Announcements: {len(ann_ids)}")

    # Notification outbox entries (simulating sent notifications)
    # Fetch some user IDs for notifications
    user_rows = fetch_all("auth_db",
        "SELECT id FROM users WHERE school_id = %s LIMIT 20", (SCHOOL_ID,))
    user_ids = [str(r[0]) for r in user_rows]

    outbox_count = 0
    for ann_id in ann_ids[:5]:  # First 5 announcements have notifications
        for uid_val in user_ids[:10]:
            statuses = ["sent", "sent", "sent", "delivered", "delivered", "failed"]
            execute("comms_db", """
                INSERT INTO notification_outbox (id, school_id, announcement_id, user_id, channel, status, retry_count, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (announcement_id, user_id, channel) DO NOTHING
            """, (uid(), SCHOOL_ID, ann_id, uid_val, random.choice(["push", "sms"]),
                  random.choice(statuses), 0, NOW))
            outbox_count += 1

    print(f"  ✅ Notification Outbox: {outbox_count}")
    return len(ann_ids)


# ═══════════════════════════════════════════════════════════
#  6. ASSESSMENT SERVICE
# ═══════════════════════════════════════════════════════════

def seed_assessments(student_ids, class_map, subject_map, teacher_ids):
    print("\n📝 Seeding Assessments (assessment_db)...")

    # Get class-student mapping from enrollments
    enrollment_rows = fetch_all("student_db",
        "SELECT student_id, class_id FROM enrollments WHERE school_id = %s AND status = 'active'", (SCHOOL_ID,))
    class_students = {}
    for sid, cid in enrollment_rows:
        cid_str = str(cid)
        if cid_str not in class_students:
            class_students[cid_str] = []
        class_students[cid_str].append(str(sid))

    assessment_ids = []
    core_subjects = ["ENG", "MAT", "SHO", "SCI", "SST"]

    for class_name, class_id in class_map.items():
        for subj_code in core_subjects:
            subj_id = subject_map.get(subj_code)
            if not subj_id:
                continue

            # Create 2 assessments per class per subject: one test, one assignment
            for atype, aname, max_marks in [("test", "Mid-Term Test", 100), ("quiz", "Class Assignment 1", 50)]:
                assess_id = uid()
                assess_date = TODAY - timedelta(days=random.randint(5, 25))
                teacher = teacher_ids[0] if teacher_ids else ADMIN_ID

                execute("assessment_db", """
                    INSERT INTO assessments (id, school_id, academic_year_id, term_id, class_id, subject_id, name, assessment_type, date, max_marks, created_by, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (assess_id, SCHOOL_ID, ACAD_YEAR_ID, TERM1_ID, class_id, subj_id,
                      f"{class_name} {aname} - {subj_code}", atype, assess_date, max_marks, teacher, NOW, NOW))
                assessment_ids.append((assess_id, class_id, max_marks))

    print(f"  ✅ Assessments: {len(assessment_ids)}")

    # Marks for each assessment
    mark_count = 0
    for assess_id, class_id, max_marks in assessment_ids:
        students_in_class = class_students.get(class_id, [])
        for sid in students_in_class:
            # 5% absent
            is_absent = random.random() < 0.05
            if is_absent:
                marks_val = None
                remarks = "Absent"
            else:
                # Normal distribution around 65%
                marks_val = min(max_marks, max(0, round(random.gauss(max_marks * 0.65, max_marks * 0.15), 1)))
                remarks = None
                if marks_val >= max_marks * 0.8:
                    remarks = random.choice(["Excellent work!", "Outstanding!", "Well done!"])
                elif marks_val < max_marks * 0.4:
                    remarks = random.choice(["Needs improvement", "Must work harder", "See me for extra help"])

            teacher = teacher_ids[0] if teacher_ids else ADMIN_ID
            execute("assessment_db", """
                INSERT INTO marks (id, school_id, assessment_id, student_id, marks, is_absent, remarks, graded_by, graded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (assessment_id, student_id) DO NOTHING
            """, (uid(), SCHOOL_ID, assess_id, sid, marks_val, is_absent, remarks, teacher, NOW))
            mark_count += 1

    print(f"  ✅ Marks: {mark_count}")


# ═══════════════════════════════════════════════════════════
#  7. REPORTING PROJECTIONS
# ═══════════════════════════════════════════════════════════

def seed_reporting(student_count, total_invoiced, total_paid, ann_count):
    print("\n📊 Seeding Reporting Projections (reporting_db)...")

    # Ensure tables exist
    try:
        fetch_all("reporting_db", "SELECT 1 FROM dashboard_stats LIMIT 1")
    except Exception:
        print("  ⚠️  Reporting tables don't exist — skipping reporting sync")
        return

    # Compute today's attendance stats
    att_rows = fetch_all("attendance_db", """
        SELECT count(*) FILTER (WHERE status IN ('P','L')) as present,
               count(*) as total
        FROM attendance_records WHERE school_id = %s AND date = %s
    """, (SCHOOL_ID, TODAY))
    today_present = att_rows[0][0] if att_rows else 0
    today_total = att_rows[0][1] if att_rows else 0

    # Dashboard stats
    execute("reporting_db", """
        INSERT INTO dashboard_stats (school_id, total_students, active_students, total_enrollments,
            attendance_today_present, attendance_today_total, total_invoiced, total_paid,
            announcements_this_month, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (school_id) DO UPDATE SET
            total_students = EXCLUDED.total_students,
            active_students = EXCLUDED.active_students,
            total_enrollments = EXCLUDED.total_enrollments,
            attendance_today_present = EXCLUDED.attendance_today_present,
            attendance_today_total = EXCLUDED.attendance_today_total,
            total_invoiced = EXCLUDED.total_invoiced,
            total_paid = EXCLUDED.total_paid,
            announcements_this_month = EXCLUDED.announcements_this_month,
            updated_at = EXCLUDED.updated_at
    """, (SCHOOL_ID, student_count, student_count, student_count,
          today_present, today_total, total_invoiced, total_paid, ann_count, NOW))
    print("  ✅ Dashboard Stats")

    # Financial summary
    execute("reporting_db", """
        INSERT INTO financial_summary (id, school_id, academic_year_id, total_invoiced, total_paid, total_outstanding, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (school_id, academic_year_id) DO UPDATE SET
            total_invoiced = EXCLUDED.total_invoiced, total_paid = EXCLUDED.total_paid,
            total_outstanding = EXCLUDED.total_outstanding, updated_at = EXCLUDED.updated_at
    """, (uid(), SCHOOL_ID, ACAD_YEAR_ID, total_invoiced, total_paid, total_invoiced - total_paid, NOW))
    print("  ✅ Financial Summary")

    # Student count projection
    execute("reporting_db", """
        INSERT INTO student_count_projection (id, school_id, academic_year_id, total_students, active_students, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (school_id, academic_year_id) DO UPDATE SET
            total_students = EXCLUDED.total_students, active_students = EXCLUDED.active_students,
            updated_at = EXCLUDED.updated_at
    """, (uid(), SCHOOL_ID, ACAD_YEAR_ID, student_count, student_count, NOW))
    print("  ✅ Student Count Projection")

    # Attendance daily aggregates (last 30 weekdays)
    agg_count = 0
    for day in range(30):
        rdate = TODAY - timedelta(days=day)
        if rdate.weekday() >= 5:
            continue
        att = fetch_all("attendance_db", """
            SELECT count(*) FILTER (WHERE status = 'P') as present,
                   count(*) FILTER (WHERE status = 'A') as absent,
                   count(*) FILTER (WHERE status = 'L') as late
            FROM attendance_records WHERE school_id = %s AND date = %s
        """, (SCHOOL_ID, rdate))
        if att and (att[0][0] + att[0][1] + att[0][2]) > 0:
            execute("reporting_db", """
                INSERT INTO attendance_daily_aggregate (id, school_id, date, present_count, absent_count, late_count, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (school_id, date) DO UPDATE SET
                    present_count = EXCLUDED.present_count, absent_count = EXCLUDED.absent_count,
                    late_count = EXCLUDED.late_count, updated_at = EXCLUDED.updated_at
            """, (uid(), SCHOOL_ID, rdate, att[0][0], att[0][1], att[0][2], NOW))
            agg_count += 1
    print(f"  ✅ Attendance Aggregates: {agg_count} days")


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    print("🚀 EduZim Full Mock Data Seed")
    print("=" * 50)

    # 1. Academics
    class_map, subject_map, teacher_ids = seed_academics()

    # 2. Students & Parents
    student_ids, parent_ids = seed_students(class_map)

    # 3. Attendance
    seed_attendance(student_ids, class_map, teacher_ids)

    # 4. Fees
    total_invoiced, total_paid = seed_fees(student_ids)

    # 5. Communications
    ann_count = seed_communications()

    # 6. Assessments
    seed_assessments(student_ids, class_map, subject_map, teacher_ids)

    # 7. Reporting
    seed_reporting(len(student_ids), total_invoiced, total_paid, ann_count)

    print("\n" + "=" * 50)
    print("🎉 Full Seed Complete!")
    print(f"  📚 Subjects: {len(subject_map)} | Classes: {len(class_map)}")
    print(f"  👥 Students: {len(student_ids)} | Parents: {len(parent_ids)}")
    print(f"  💰 Invoiced: ${total_invoiced:,.0f} | Paid: ${total_paid:,.0f}")
    print(f"  📢 Announcements: {ann_count}")
    print(f"  📝 Assessments: {len(subject_map) * len(class_map) * 2} approx")
    print()


if __name__ == "__main__":
    main()
