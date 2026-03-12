#!/usr/bin/env python3
import psycopg2
import uuid
import os

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "eduzim"),
    "password": os.environ.get("DB_PASS", "eduzim_secret"),
    "port": os.environ.get("DB_PORT", "5432"),
    "dbname": "auth_db"
}

def seed():
    print("🌱 Seeding Baseline Roles and Permissions...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # 1. Roles
    roles = [
        ("SchoolAdmin", "Full administrative access and reporting."),
        ("Teacher", "Teaching and grading permissions."),
        ("Parent", "View child progress and financials."),
        ("Student", "Student portal access.")
    ]

    role_ids = {}
    for name, desc in roles:
        rid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO roles (id, name, description) VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING RETURNING id",
            (rid, name, desc)
        )
        res = cur.fetchone()
        if res:
            role_ids[name] = res[0]
        else:
            cur.execute("SELECT id FROM roles WHERE name = %s", (name,))
            role_ids[name] = cur.fetchone()[0]

    # 2. Permissions (Matching api-gateway requirements)
    permissions = [
        ("school:manage", "Manage school settings, years, terms", "school", "manage"),
        ("student:write", "Create/Update students and parents", "student", "write"),
        ("student:read", "View student and parent profiles", "student", "read"),
        ("attendance:write", "Mark and sync attendance", "attendance", "write"),
        ("attendance:read", "View attendance records", "attendance", "read"),
        ("fees:write", "Manage fees and invoices", "fees", "write"),
        ("fees:read", "View financial summaries", "fees", "read"),
        ("comm:write", "Send communications and announcements", "comm", "write"),
        ("comm:read", "View communication feed", "comm", "read"),
        ("report:read", "View dashboard and summary reports", "report", "read"),
        ("report:admin", "Rebuild projections and advanced reports", "report", "admin"),
        ("assessment:write", "Manage assessments and marks", "assessment", "write"),
        ("assessment:read", "View student assessments", "assessment", "read"),
    ]

    perm_ids = {}
    for name, desc, res, act in permissions:
        pid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO permissions (id, name, description, resource, action) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (name) DO NOTHING RETURNING id",
            (pid, name, desc, res, act)
        )
        r = cur.fetchone()
        if r:
            perm_ids[name] = r[0]
        else:
            cur.execute("SELECT id FROM permissions WHERE name = %s", (name,))
            perm_ids[name] = cur.fetchone()[0]

    # 3. Associate Permissions to Roles
    # SchoolAdmin gets all permissions
    for p_id in perm_ids.values():
        cur.execute(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (role_ids["SchoolAdmin"], p_id)
        )

    # Teacher
    teacher_perms = ["student:read", "attendance:write", "attendance:read", "report:read", "assessment:write", "assessment:read", "comm:read"]
    for p_name in teacher_perms:
        cur.execute(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (role_ids["Teacher"], perm_ids[p_name])
        )

    # Parent
    parent_perms = ["student:read", "report:read", "fees:read", "comm:read", "assessment:read"]
    for p_name in parent_perms:
        cur.execute(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (role_ids["Parent"], perm_ids[p_name])
        )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Baseline roles and permissions seeded successfully.")

if __name__ == "__main__":
    seed()
