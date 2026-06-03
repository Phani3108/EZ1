#!/usr/bin/env python3
"""
EduZim — Demo Data Seeder (consolidated-schema edition)
=======================================================
Populates the CURRENT, post-consolidation databases with realistic
Zimbabwean school data so every dashboard and list page shows live numbers.

Unlike the legacy scripts/rich-seed.py (which targets the pre-consolidation
DB names school_db/student_db/attendance_db and is broken), this script writes
to the real DBs:

    academics_db  — schools, academic_years, terms, classes, subjects,
                    students, parents, student_parents, enrollments,
                    attendance_records
    fees_db       — fee_structures, fee_items, invoices, payments
    comms_db      — announcements
    reporting_db  — dashboard_stats, attendance_daily_aggregate,
                    financial_summary  (the CQRS read-model the dashboard reads)

Idempotent: deletes the demo school's rows first, then re-inserts. Safe to
re-run. Deterministic (fixed RNG seed) so re-runs produce the same data.

Run it INSIDE the academics container (has psycopg2 + in-network DB access):

    docker exec -i eduzim-academics python3 - < scripts/demo-seed.py

or from the host (Postgres is published on :15432):

    DB_HOST=localhost DB_PORT=15432 python3 scripts/demo-seed.py
"""
import os
import uuid
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import psycopg2

# ── Connection ────────────────────────────────────────────────────────
DB = {
    "host": os.environ.get("DB_HOST", "postgres"),
    "port": os.environ.get("DB_PORT", "5432"),
    "user": os.environ.get("DB_USER", "eduzim"),
    "password": os.environ.get("DB_PASS", "eduzim_secret"),
}

# Must match the school_id baked into the dev admin's JWT (scripts/dev-seed.sh).
SCHOOL_ID = "11111111-1111-1111-1111-111111111111"
YEAR_ID = "22222222-2222-2222-2222-222222222222"
TERM1_ID = "33333333-3333-3333-3333-333333333331"
TERM2_ID = "33333333-3333-3333-3333-333333333332"
TERM3_ID = "33333333-3333-3333-3333-333333333333"
FEE_STRUCT_ID = "44444444-4444-4444-4444-444444444444"
ADMIN_USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

NOW = datetime.now(timezone.utc)
TODAY = date.today()

random.seed(42)  # deterministic

# ── Zimbabwean name library ───────────────────────────────────────────
SURNAMES = ["Moyo", "Sibanda", "Ndlovu", "Mutasa", "Gumbo", "Zhou", "Mpofu",
            "Ncube", "Dube", "Maphosa", "Phiri", "Chipadze", "Makoni", "Nkomo",
            "Khumalo", "Bhebhe", "Nyoni", "Sigauke", "Marange", "Shumba",
            "Hungwe", "Sithole", "Chitepo", "Mujuru", "Chinaka", "Madziva",
            "Goredema", "Mangwende", "Zvobgo", "Muchena"]
FIRST_M = ["Tendai", "Blessing", "Tinashe", "Farai", "Simba", "Takudzwa",
           "Kudakwashe", "Munashe", "Tapiwa", "Takunda", "Tatenda", "Anesu",
           "Tanaka", "Lovemore", "Gift", "Knowledge", "Prince", "Dumisani",
           "Bongani", "Nkosana", "Mandla", "Sifiso", "Lwazi", "Brighton"]
FIRST_F = ["Chipo", "Tariro", "Rutendo", "Nomsa", "Thandiwe", "Memory",
           "Patience", "Joy", "Ruvimbo", "Sekai", "Vimbai", "Yeukai", "Zanele",
           "Sharon", "Netsai", "Fungai", "Danai", "Nonhlanhla", "Sithembile",
           "Thembi", "Nozipho", "Gugu", "Rumbidzai", "Precious"]
SUBJECTS = [("English", "ENG"), ("Mathematics", "MAT"), ("Combined Science", "SCI"),
            ("Shona", "SHO"), ("Ndebele", "NDE"), ("Geography", "GEO"),
            ("History", "HIS"), ("Physics", "PHY"), ("Chemistry", "CHM"),
            ("Biology", "BIO"), ("Heritage Studies", "HER"),
            ("Agriculture", "AGR")]
CLASS_DEFS = [("Form 1A", "A", 1), ("Form 1B", "B", 1), ("Form 2A", "A", 2),
              ("Form 2B", "B", 2), ("Form 3A", "A", 3), ("Form 3B", "B", 3),
              ("Form 4A", "A", 4), ("Form 4B", "B", 4)]
STUDENTS_PER_CLASS = 30
ANNOUNCEMENTS = [
    ("Term 1 Opening Day", "School reopens Monday. Lessons resume at 07:30. All learners must be in full uniform."),
    ("Fees Payment Reminder", "Term 1 fees are due by the end of week 3. Please settle balances at the bursar's office."),
    ("Parents' Consultation Day", "Parents are invited to meet subject teachers on the last Friday of the month."),
    ("Sports Gala", "The inter-house athletics gala will be held at the school grounds. Spectators welcome."),
    ("ZIMSEC Registration", "Form 4 candidates must complete ZIMSEC examination registration this week."),
    ("Prize-Giving Ceremony", "The annual prize-giving ceremony honours top performers across all forms."),
]


def conn(dbname):
    c = psycopg2.connect(dbname=dbname, **DB)
    c.autocommit = False
    return c


def recent_weekdays(n):
    """Return the most recent n weekdays ending today (oldest first)."""
    out, d = [], TODAY
    while len(out) < n:
        if d.weekday() < 5:  # Mon-Fri
            out.append(d)
        d -= timedelta(days=1)
    return list(reversed(out))


def seed():
    students = []   # (id, code, first, last, gender, dob, class_id)
    parents = []    # (id, first, last, phone, rel)
    classes = []    # (id, name, section)
    att_days = recent_weekdays(15)

    # ── academics_db ──────────────────────────────────────────────────
    ac = conn("academics_db")
    cur = ac.cursor()

    # Idempotency: clear this school's demo rows (child → parent order).
    for tbl in ["attendance_records", "enrollments", "student_parents",
                "students", "parents", "classes", "subjects", "terms",
                "academic_years"]:
        cur.execute(f"DELETE FROM {tbl} WHERE school_id = %s", (SCHOOL_ID,))

    # School (upsert — JWT references this id).
    cur.execute("""
        INSERT INTO schools (id, name, country, timezone, province_code,
            school_type, tenancy_tier, maintenance_mode, principal_name,
            address, phone, email, founded_year, is_active, is_live,
            created_at, updated_at)
        VALUES (%s, 'Harare Central Secondary School', 'ZW', 'Africa/Harare',
            'HRE', 'SECONDARY', 'shared', false, 'Mr. T. Chiwenga',
            '12 Samora Machel Ave, Harare', '+263 24 2700000',
            'admin@school.ac.zw', 1962, true, true, %s, %s)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name,
            is_active = true, updated_at = EXCLUDED.updated_at
    """, (SCHOOL_ID, NOW, NOW))

    # Academic year + 3 terms (Term 1 active).
    cur.execute("""INSERT INTO academic_years (id, school_id, name, start_date,
        end_date, is_active, created_at, updated_at)
        VALUES (%s,%s,'2026',%s,%s,true,%s,%s)""",
        (YEAR_ID, SCHOOL_ID, date(2026, 1, 12), date(2026, 12, 4), NOW, NOW))
    terms = [(TERM1_ID, "Term 1", date(2026, 1, 12), date(2026, 4, 10), True),
             (TERM2_ID, "Term 2", date(2026, 5, 5), date(2026, 8, 7), False),
             (TERM3_ID, "Term 3", date(2026, 9, 8), date(2026, 12, 4), False)]
    for tid, name, sd, ed, active in terms:
        cur.execute("""INSERT INTO terms (id, school_id, academic_year_id, name,
            start_date, end_date, is_active, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (tid, SCHOOL_ID, YEAR_ID, name, sd, ed, active, NOW))

    # Subjects.
    for name, code in SUBJECTS:
        cur.execute("""INSERT INTO subjects (id, school_id, name, code,
            is_active, created_at) VALUES (%s,%s,%s,%s,true,%s)""",
            (str(uuid.uuid4()), SCHOOL_ID, name, code, NOW))

    # Classes.
    for name, section, grade in CLASS_DEFS:
        cid = str(uuid.uuid4())
        classes.append((cid, name, section))
        cur.execute("""INSERT INTO classes (id, school_id, name, section,
            grade_level, capacity, is_active, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,true,%s,%s)""",
            (cid, SCHOOL_ID, name, section, grade, 40, NOW, NOW))

    # Students + parents + enrollments.
    code_n = 1000
    for cid, cname, _ in classes:
        for _ in range(STUDENTS_PER_CLASS):
            gender = random.choice(["Male", "Female"])
            first = random.choice(FIRST_M if gender == "Male" else FIRST_F)
            last = random.choice(SURNAMES)
            code_n += 1
            sid = str(uuid.uuid4())
            code = f"HCS{code_n}"
            age = random.randint(12, 18)
            dob = date(2026 - age, random.randint(1, 12), random.randint(1, 28))
            adm = date(2026 - random.randint(0, 4), 1, 15)
            students.append((sid, code, first, last, gender, cid))
            cur.execute("""INSERT INTO students (id, school_id, student_code,
                first_name, last_name, dob, gender, admission_date, status,
                created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'ACTIVE',%s,%s)""",
                (sid, SCHOOL_ID, code, first, last, dob, gender, adm, NOW, NOW))

            # Parent (one primary guardian per student).
            pid = str(uuid.uuid4())
            prel = random.choice(["MOTHER", "FATHER", "GUARDIAN"])
            pfirst = random.choice(FIRST_F if prel == "MOTHER" else FIRST_M)
            phone = f"+2637{random.randint(10000000, 99999999)}"
            cur.execute("""INSERT INTO parents (id, school_id, first_name,
                last_name, phone, email, relationship_type, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (pid, SCHOOL_ID, pfirst, last, phone,
                 f"{pfirst.lower()}.{last.lower()}@example.co.zw", prel, NOW))
            cur.execute("""INSERT INTO student_parents (id, school_id,
                student_id, parent_id, is_primary, created_at)
                VALUES (%s,%s,%s,%s,true,%s)""",
                (str(uuid.uuid4()), SCHOOL_ID, sid, pid, NOW))

            # Enrollment.
            cur.execute("""INSERT INTO enrollments (id, school_id, student_id,
                class_id, academic_year_id, enrolled_at, status, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,'ENROLLED',%s)""",
                (str(uuid.uuid4()), SCHOOL_ID, sid, cid, YEAR_ID,
                 date(2026, 1, 12), NOW))

    # Attendance — last 15 weekdays, ~92% present / 5% absent / 3% late.
    daily_counts = {}  # day -> [present, absent, late]
    for d in att_days:
        p = a = l = 0
        for sid, _, _, _, _, cid in students:
            r = random.random()
            status = "P" if r < 0.92 else ("L" if r < 0.95 else "A")
            if status == "P":
                p += 1
            elif status == "A":
                a += 1
            else:
                l += 1
            cur.execute("""INSERT INTO attendance_records (id, school_id,
                student_id, class_id, date, status, period_number,
                marked_by_user_id, last_modified_at, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,0,%s,%s,%s,%s)""",
                (str(uuid.uuid4()), SCHOOL_ID, sid, cid, d, status,
                 ADMIN_USER_ID, NOW, NOW, NOW))
        daily_counts[d] = [p, a, l]

    ac.commit()
    cur.close()
    ac.close()

    # ── fees_db ───────────────────────────────────────────────────────
    fe = conn("fees_db")
    cur = fe.cursor()
    # fee_items has no school_id — it hangs off fee_structures.
    cur.execute("""DELETE FROM fee_items WHERE fee_structure_id IN
        (SELECT id FROM fee_structures WHERE school_id = %s)""", (SCHOOL_ID,))
    for tbl in ["payments", "invoices", "fee_structures"]:
        cur.execute(f"DELETE FROM {tbl} WHERE school_id = %s", (SCHOOL_ID,))

    cur.execute("""INSERT INTO fee_structures (id, school_id, academic_year_id,
        term_id, name, is_active, created_at)
        VALUES (%s,%s,%s,%s,'Term 1 Tuition 2026',true,%s)""",
        (FEE_STRUCT_ID, SCHOOL_ID, YEAR_ID, TERM1_ID, NOW))
    cur.execute("""INSERT INTO fee_items (id, fee_structure_id, label, amount,
        currency) VALUES (%s,%s,'Tuition',200.00,'USD')""",
        (str(uuid.uuid4()), FEE_STRUCT_ID))
    cur.execute("""INSERT INTO fee_items (id, fee_structure_id, label, amount,
        currency) VALUES (%s,%s,'Levy',50.00,'USD')""",
        (str(uuid.uuid4()), FEE_STRUCT_ID))

    FEE_TOTAL = Decimal("250.00")
    total_invoiced = Decimal("0")
    total_paid = Decimal("0")
    for sid, _, _, _, _, _ in students:
        inv_id = str(uuid.uuid4())
        roll = random.random()
        if roll < 0.55:        # fully paid
            paid, status = FEE_TOTAL, "PAID"
        elif roll < 0.80:      # partial
            paid, status = Decimal("150.00"), "PARTIAL"
        else:                  # unpaid
            paid, status = Decimal("0.00"), "PENDING"
        total_invoiced += FEE_TOTAL
        total_paid += paid
        cur.execute("""INSERT INTO invoices (id, school_id, student_id,
            fee_structure_id, total_amount, paid_amount, currency, due_date,
            status, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,'USD',%s,%s,%s,%s)""",
            (inv_id, SCHOOL_ID, sid, FEE_STRUCT_ID, FEE_TOTAL, paid,
             date(2026, 2, 6), status, NOW, NOW))
        if paid > 0:
            cur.execute("""INSERT INTO payments (id, school_id, invoice_id,
                amount, currency, method, reference, paid_at, created_at)
                VALUES (%s,%s,%s,%s,'USD',%s,%s,%s,%s)""",
                (str(uuid.uuid4()), SCHOOL_ID, inv_id, paid,
                 random.choice(["CASH", "ECOCASH", "BANK_TRANSFER"]),
                 f"RCP{random.randint(100000,999999)}", NOW, NOW))
    fe.commit()
    cur.close()
    fe.close()

    # ── comms_db ──────────────────────────────────────────────────────
    co = conn("comms_db")
    cur = co.cursor()
    cur.execute("DELETE FROM announcements WHERE school_id = %s", (SCHOOL_ID,))
    for i, (title, body) in enumerate(ANNOUNCEMENTS):
        created = NOW - timedelta(days=i * 3)
        cur.execute("""INSERT INTO announcements (id, school_id, title, body,
            audience_type, created_by, created_at)
            VALUES (%s,%s,%s,%s,'ALL',%s,%s)""",
            (str(uuid.uuid4()), SCHOOL_ID, title, body, ADMIN_USER_ID, created))
    co.commit()
    cur.close()
    co.close()

    # ── reporting_db (CQRS read-model the dashboard queries) ──────────
    rep = conn("reporting_db")
    cur = rep.cursor()
    for tbl in ["dashboard_stats", "attendance_daily_aggregate",
                "financial_summary"]:
        cur.execute(f"DELETE FROM {tbl} WHERE school_id = %s", (SCHOOL_ID,))

    today_present, today_absent, today_late = daily_counts[att_days[-1]]
    today_total = today_present + today_absent + today_late
    cur.execute("""INSERT INTO dashboard_stats (school_id, total_students,
        active_students, total_enrollments, attendance_today_present,
        attendance_today_total, total_invoiced, total_paid,
        announcements_this_month, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (SCHOOL_ID, len(students), len(students), len(students),
         today_present, today_total, total_invoiced, total_paid,
         len(ANNOUNCEMENTS), NOW))

    for d, (p, a, l) in daily_counts.items():
        cur.execute("""INSERT INTO attendance_daily_aggregate (id, school_id,
            date, present_count, absent_count, late_count, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (str(uuid.uuid4()), SCHOOL_ID, d, p, a, l, NOW))

    cur.execute("""INSERT INTO financial_summary (id, school_id,
        academic_year_id, total_invoiced, total_paid, total_outstanding,
        updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (str(uuid.uuid4()), SCHOOL_ID, YEAR_ID, total_invoiced, total_paid,
         total_invoiced - total_paid, NOW))
    rep.commit()
    cur.close()
    rep.close()

    print("✅ Demo data seeded for Harare Central Secondary School")
    print(f"   Students:      {len(students)}")
    print(f"   Classes:       {len(classes)}")
    print(f"   Subjects:      {len(SUBJECTS)}")
    print(f"   Attendance:    {len(students) * len(att_days)} records "
          f"over {len(att_days)} school days")
    print(f"   Invoiced:      ${total_invoiced}   Collected: ${total_paid}   "
          f"Outstanding: ${total_invoiced - total_paid}")
    print(f"   Announcements: {len(ANNOUNCEMENTS)}")
    print(f"   Today's attendance: {today_present}/{today_total} present")


if __name__ == "__main__":
    seed()
