#!/usr/bin/env python3
import psycopg2
import uuid
import random
import os
from datetime import date, datetime, timedelta, timezone

# ─── Configuration ───
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "eduzim"),
    "password": os.environ.get("DB_PASS", "eduzim_secret"),
    "port": os.environ.get("DB_PORT", "5432")
}

# ─── Data Library ───
SURNAMES = ["Moyo", "Sibanda", "Ndlovu", "Mutasa", "Gumbo", "Zhou", "Mpofu", "Ncube", "Dube", "Maphosa", "Phiri", "Mokoena", "Zondo", "Chipadze", "Makoni", "Tsvangirai", "Mugabe", "Nkomo", "Mnangagwa", "Chamisa", "Khumalo", "Bhebhe", "Nyoni", "Sigauke", "Marange", "Chidzero", "Mudenge", "Mahachi", "Shumba", "Hungwe", "Dlamini", "Zuma", "Sithole", "Muzorewa", "Tekere", "Banana", "Chitepo", "Tongogara", "Sekeramayi", "Mujuru", "Chinaka"]
FIRST_NAMES_M = ["Tendai", "Blessing", "Tinashe", "Farai", "Simba", "Takudzwa", "Itai", "Kudakwashe", "Munashe", "Tapiwa", "Takunda", "Tanyaradzwa", "Tatenda", "Anesu", "Tanaka", "Terrence", "Lovemore", "Gift", "Knowledge", "Prince", "Thabo", "Dumisani", "Melusi", "Mpumelelo", "Sbusiso", "Jabulani", "Mthokozisi", "Vusumuzi", "Bongani", "Nkosi", "Sifiso", "Lwazi", "Mandla", "Nqobile", "Thabani"]
FIRST_NAMES_F = ["Chipo", "Tariro", "Rutendo", "Nomsa", "Thandiwe", "Gugulethu", "Memory", "Patience", "Joy", "Ruvimbo", "Sekai", "Vimbai", "Yeukai", "Zanele", "Sharon", "Netsai", "Hazvinei", "Fungai", "Danai", "Busi", "Nonhlanhla", "Sithembile", "Londiwe", "Nomalanga", "Thembi", "Sipho", "Nozipho", "Sizani", "Gugu", "Zariro"]
SUBJECTS = ["English", "Mathematics", "Science", "Shona", "Ndebele", "Social Studies", "History", "Geography", "Physics", "Chemistry", "Biology", "Heritage Studies", "Physical Education"]

# ─── Helpers ───
def get_conn(db_name):
    return psycopg2.connect(dbname=db_name, **DB_CONFIG)

def execute_sql(db_name, sql, params=None):
    with get_conn(db_name) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()

def fetch_all(db_name, sql, params=None):
    with get_conn(db_name) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

# ─── Seeding Logic ───
SCHOOL_ID = "11111111-1111-1111-1111-111111111111"
ACADEMIC_YEAR_ID = "22222222-2222-2222-2222-222222222222"
TERM_ID = "33333333-3333-3333-3333-333333333333"
ADMIN_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
NOW = datetime.now(timezone.utc)
TODAY = date.today()

def seed():
    print("🚀 Starting Clean & High-Fidelity Zimbabwean Seed...")

    # 0. Cleanup
    for db in ["school_db", "attendance_db", "fees_db", "student_db", "auth_db", "assessment_db", "comms_db", "reporting_db"]:
        try:
            if db == "school_db":
                execute_sql(db, "DELETE FROM class_teacher_assignments WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM classes WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM subjects WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM terms WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM academic_years WHERE school_id = %s", (SCHOOL_ID,))
            elif db == "attendance_db":
                execute_sql(db, "DELETE FROM attendance_records WHERE school_id = %s", (SCHOOL_ID,))
            elif db == "fees_db":
                execute_sql(db, "DELETE FROM payments WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM invoices WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM fee_items WHERE fee_structure_id IN (SELECT id FROM fee_structures WHERE school_id = %s)", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM fee_structures WHERE school_id = %s", (SCHOOL_ID,))
            elif db == "student_db":
                execute_sql(db, "DELETE FROM student_parents WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM enrollments WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM parents WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM students WHERE school_id = %s", (SCHOOL_ID,))
            elif db == "auth_db":
                execute_sql(db, "DELETE FROM user_roles WHERE user_id IN (SELECT id FROM users WHERE school_id = %s AND (id != %s))", (SCHOOL_ID, ADMIN_ID))
                execute_sql(db, "DELETE FROM users WHERE school_id = %s AND id != %s", (SCHOOL_ID, ADMIN_ID))
            elif db == "assessment_db":
                execute_sql(db, "DELETE FROM marks WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM assessments WHERE school_id = %s", (SCHOOL_ID,))
            elif db == "comms_db":
                execute_sql(db, "DELETE FROM notification_outbox WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM announcements WHERE school_id = %s", (SCHOOL_ID,))
            elif db == "reporting_db":
                execute_sql(db, "DELETE FROM dashboard_stats WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM attendance_daily_aggregate WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM financial_summary WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM student_count_projection WHERE school_id = %s", (SCHOOL_ID,))
                execute_sql(db, "DELETE FROM processed_events WHERE school_id = %s", (SCHOOL_ID,))
        except Exception as e:
            pass

    # 1. School & Structural
    execute_sql("school_db", "INSERT INTO schools (id, name, country, timezone, is_active, created_at, updated_at) VALUES (%s, 'Harare International Academy', 'ZW', 'Africa/Harare', true, %s, %s) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name", (SCHOOL_ID, NOW, NOW))
    execute_sql("school_db", "INSERT INTO academic_years (id, school_id, name, start_date, end_date, is_active, created_at, updated_at) VALUES (%s, %s, '2026 Academic Year', '2026-01-01', '2026-12-31', true, %s, %s)", (ACADEMIC_YEAR_ID, SCHOOL_ID, NOW, NOW))
    execute_sql("school_db", "INSERT INTO terms (id, school_id, academic_year_id, name, start_date, end_date, is_active, created_at) VALUES (%s, %s, %s, 'Term 1', '2026-01-01', '2026-04-30', true, %s)", (TERM_ID, SCHOOL_ID, ACADEMIC_YEAR_ID, NOW))

    subjects = []
    for sname in SUBJECTS:
        sid = str(uuid.uuid4())
        # Better code generation: handle Phys Ed clash
        code = sname[:5].upper()
        if sname == "Physical Education": code = "PE"
        if sname == "Heritage Studies": code = "HERIT"
        
        execute_sql("school_db", "INSERT INTO subjects (id, school_id, name, code, is_active, created_at) VALUES (%s, %s, %s, %s, true, %s)", (sid, SCHOOL_ID, sname, code, NOW))
        subjects.append(sid)

    # 15 Classes
    classes = []
    for i in range(1, 16):
        cid = str(uuid.uuid4())
        name = f"Grade {i}" if i <= 7 else f"Form {i-7}"
        execute_sql("school_db", "INSERT INTO classes (id, school_id, name, section, capacity, is_active, created_at, updated_at) VALUES (%s, %s, %s, 'A', 40, true, %s, %s)", (cid, SCHOOL_ID, name, NOW, NOW))
        classes.append(cid)

    # 2. Staff (30 Teachers)
    pass_hash = '$2b$12$iRHA4Bsr4JDHNH7GqzgNoeTuqBhad8GvZPFJxD7vrZCL6EUBFT/9O' # pass123
    teachers = []
    for i in range(30):
        uid = str(uuid.uuid4())
        gender = random.choice(["M", "F"])
        names = FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F
        fn, ln = random.choice(names), random.choice(SURNAMES)
        email = f"teacher.{i+1}@eduzim.zw"
        execute_sql("auth_db", "INSERT INTO users (id, email, full_name, password_hash, school_id, is_active, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, true, %s, %s)", (uid, email, f"{fn} {ln}", pass_hash, SCHOOL_ID, NOW, NOW))
        execute_sql("auth_db", "INSERT INTO user_roles (user_id, role_id) SELECT %s, id FROM roles WHERE name = 'Teacher'", (uid,))
        teachers.append(uid)
        if i < 15: # Lead 15 classes
            execute_sql("school_db", "INSERT INTO class_teacher_assignments (id, school_id, class_id, teacher_user_id, academic_year_id, created_at) VALUES (%s, %s, %s, %s, %s, %s)", (str(uuid.uuid4()), SCHOOL_ID, classes[i], uid, ACADEMIC_YEAR_ID, NOW))

    # 3. Parents (60)
    parents = []
    for i in range(60):
        uid = str(uuid.uuid4())
        gender = random.choice(["M", "F"])
        names = FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F
        fn, ln = random.choice(names), random.choice(SURNAMES)
        email = f"parent.{i+1}@eduzim.zw"
        execute_sql("auth_db", "INSERT INTO users (id, email, full_name, password_hash, school_id, is_active, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, true, %s, %s)", (uid, email, f"{fn} {ln}", pass_hash, SCHOOL_ID, NOW, NOW))
        execute_sql("auth_db", "INSERT INTO user_roles (user_id, role_id) SELECT %s, id FROM roles WHERE name = 'Parent'", (uid,))
        pid = str(uuid.uuid4())
        execute_sql("student_db", "INSERT INTO parents (id, school_id, first_name, last_name, phone, email, relationship_type, user_id, created_at) VALUES (%s, %s, %s, %s, %s, %s, 'GUARDIAN', %s, %s)", (pid, SCHOOL_ID, fn, ln, f"+26377{random.randint(1000000, 9999999)}", email, uid, NOW))
        parents.append(pid)

    # 4. Students (100)
    student_list = []
    for i in range(100):
        sid = str(uuid.uuid4())
        gender = random.choice(["MALE", "FEMALE"])
        names = FIRST_NAMES_M if gender == "MALE" else FIRST_NAMES_F
        fn, ln = random.choice(names), random.choice(SURNAMES)
        code = f"ADM{2026000 + i}"
        cid = random.choice(classes)
        # Random status for a few students to show variety in lists
        status = "ACTIVE" if i < 95 else "INACTIVE"
        execute_sql("student_db", "INSERT INTO students (id, school_id, student_code, first_name, last_name, gender, status, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (sid, SCHOOL_ID, code, fn, ln, gender, status, NOW, NOW))
        execute_sql("student_db", "INSERT INTO enrollments (id, school_id, student_id, class_id, academic_year_id, status, enrolled_at, created_at) VALUES (%s, %s, %s, %s, %s, 'ENROLLED', %s, %s)", (str(uuid.uuid4()), SCHOOL_ID, sid, cid, ACADEMIC_YEAR_ID, TODAY - timedelta(days=60), NOW))
        # Assign 1 or 2 unique parents
        pcount = random.choice([1, 1, 1, 2])
        chosen_parents = random.sample(parents, pcount)
        for idx, pid in enumerate(chosen_parents):
            execute_sql("student_db", "INSERT INTO student_parents (id, school_id, student_id, parent_id, is_primary, created_at) VALUES (%s, %s, %s, %s, %s, %s)", (str(uuid.uuid4()), SCHOOL_ID, sid, pid, idx==0, NOW))
        student_list.append((sid, cid, status))

    # 5. Massive Attendance (Last 30 days)
    print("  📅 Seeding Attendance (30 days)...")
    attendance_stats = {"present": 0, "total": 0}
    for day in range(30):
        rdate = TODAY - timedelta(days=day)
        if rdate.weekday() >= 5: continue # Skip weekends
        
        day_present = 0
        day_total = 0
        for sid, cid, status in student_list:
            if status != "ACTIVE": continue
            # Dropout risk logic: a few students have high absenteeism
            is_risk_student = hash(sid) % 10 == 0 
            if is_risk_student:
                stat = random.choice(["A", "A", "P", "L", "A"])
            else:
                stat = random.choice(["P", "P", "P", "P", "P", "P", "L", "A"])
            
            execute_sql("attendance_db", "INSERT INTO attendance_records (id, school_id, student_id, class_id, date, status, last_modified_at, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", (str(uuid.uuid4()), SCHOOL_ID, sid, cid, rdate, stat, NOW, NOW, NOW))
            
            if day == 0:
                attendance_stats["total"] += 1
                if stat in ["P", "L"]: attendance_stats["present"] += 1
            
            if stat in ["P", "L"]: day_present += 1
            day_total += 1
            
        # Aggregate for historical charts
        rate = day_present / max(day_total, 1)
        execute_sql("reporting_db", """
            INSERT INTO attendance_daily_aggregate (id, school_id, date, present_count, absent_count, late_count, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (school_id, date) DO UPDATE SET
                present_count = EXCLUDED.present_count,
                absent_count = EXCLUDED.absent_count,
                late_count = EXCLUDED.late_count,
                updated_at = EXCLUDED.updated_at
        """, (str(uuid.uuid4()), SCHOOL_ID, rdate, day_present, day_total - day_present, 0, NOW))

    # 6. Fees & Invoices (Realistic 6 month history)
    print("  💰 Seeding Financials...")
    fsid = str(uuid.uuid4())
    execute_sql("fees_db", "INSERT INTO fee_structures (id, school_id, academic_year_id, term_id, name, is_active, created_at) VALUES (%s, %s, %s, %s, '2026 Term 1 Tuition', true, %s)", (fsid, SCHOOL_ID, ACADEMIC_YEAR_ID, TERM_ID, NOW))
    execute_sql("fees_db", "INSERT INTO fee_items (id, fee_structure_id, label, amount, currency) VALUES (%s, %s, 'Tuition', 350.00, 'USD'), (%s, %s, 'Facility Levy', 50.00, 'USD')", (str(uuid.uuid4()), fsid, str(uuid.uuid4()), fsid))
    
    total_invoiced = 0
    total_paid = 0
    for sid, cid, status in student_list:
        if status != "ACTIVE": continue
        invid = str(uuid.uuid4())
        # Dropout risk: 10% haven't paid at all
        is_poor = hash(sid) % 10 == 0
        paid_amount = 0.0 if is_poor else random.choice([400.0, 400.0, 400.0, 200.0, 150.0])
        total_invoiced += 400.0
        total_paid += paid_amount
        
        stat = "PAID" if paid_amount == 400.0 else ("PARTIAL" if paid_amount > 0 else "PENDING")
        execute_sql("fees_db", "INSERT INTO invoices (id, school_id, student_id, fee_structure_id, total_amount, paid_amount, currency, due_date, status, created_at, updated_at) VALUES (%s, %s, %s, %s, 400.0, %s, 'USD', %s, %s, %s, %s)", (invid, SCHOOL_ID, sid, fsid, paid_amount, TODAY + timedelta(days=15), stat, NOW, NOW))
        if paid_amount > 0:
            execute_sql("fees_db", "INSERT INTO payments (id, school_id, invoice_id, amount, currency, method, paid_at, created_at) VALUES (%s, %s, %s, %s, 'USD', 'CASH', %s, %s)", (str(uuid.uuid4()), SCHOOL_ID, invid, paid_amount, NOW, NOW))

    # 7. Assessments (Denser results)
    print("  📝 Seeding Assessments...")
    for cid in classes:
        for itest in range(3):
            aid = str(uuid.uuid4())
            subid = random.choice(subjects)
            tid = random.choice(teachers)
            atype = random.choice(["QUIZ", "TEST", "EXAM"])
            execute_sql("assessment_db", "INSERT INTO assessments (id, school_id, academic_year_id, term_id, class_id, subject_id, name, assessment_type, date, max_marks, created_by, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 100, %s, %s, %s)", (aid, SCHOOL_ID, ACADEMIC_YEAR_ID, TERM_ID, cid, subid, f"{atype} {itest+1}", atype, TODAY - timedelta(days=random.randint(5, 40)), tid, NOW, NOW))
            
            class_students = [s[0] for s in student_list if s[1] == cid]
            for sid in class_students:
                # Academic risk: 10% students failing
                is_failing = hash(sid) % 10 == 0
                mark = random.randint(20, 50) if is_failing else random.randint(60, 98)
                execute_sql("assessment_db", "INSERT INTO marks (id, school_id, assessment_id, student_id, marks, is_absent, graded_by, graded_at) VALUES (%s, %s, %s, %s, %s, false, %s, %s)", (str(uuid.uuid4()), SCHOOL_ID, aid, sid, mark, tid, NOW))

    # 8. Announcements
    for _ in range(8):
        execute_sql("comms_db", "INSERT INTO announcements (id, school_id, title, body, audience_type, created_by, created_at) VALUES (%s, %s, %s, %s, 'ALL', %s, %s)", (str(uuid.uuid4()), SCHOOL_ID, f"Notification: {random.choice(['Term meeting', 'Sport day', 'Public holiday', 'Fee deadline'])}", "Detailed message about school events and requirements.", ADMIN_ID, NOW))

    # 9. Final Dashboard Sync
    print("  📊 Final Reporting Sync...")
    execute_sql("reporting_db", """
        INSERT INTO dashboard_stats (
            school_id, total_students, active_students, total_enrollments,
            attendance_today_present, attendance_today_total, total_invoiced,
            total_paid, announcements_this_month, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    """, (
        SCHOOL_ID, 100, 100, 100,
        attendance_stats["present"], attendance_stats["total"], total_invoiced, total_paid,
        8, NOW
    ))
    execute_sql("reporting_db", """
            INSERT INTO financial_summary (id, school_id, academic_year_id, total_invoiced, total_paid, total_outstanding, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (school_id, academic_year_id) DO UPDATE SET
                total_invoiced = EXCLUDED.total_invoiced,
                total_paid = EXCLUDED.total_paid,
                total_outstanding = EXCLUDED.total_outstanding,
                updated_at = EXCLUDED.updated_at
        """, (str(uuid.uuid4()), SCHOOL_ID, ACADEMIC_YEAR_ID, total_invoiced, total_paid, total_invoiced - total_paid, NOW))
    execute_sql("reporting_db", """
        INSERT INTO student_count_projection (id, school_id, academic_year_id, total_students, active_students, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (school_id, academic_year_id) DO UPDATE SET
            total_students = EXCLUDED.total_students,
            active_students = EXCLUDED.active_students,
            updated_at = EXCLUDED.updated_at
    """, (str(uuid.uuid4()), SCHOOL_ID, ACADEMIC_YEAR_ID, 100, 100, NOW))

    print("\n🎉 High-Fidelity Seeding Complete!")

if __name__ == "__main__":
    seed()
