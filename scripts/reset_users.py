#!/usr/bin/env python3
"""Reset dev users with simple credentials."""
import psycopg2
from passlib.context import CryptContext

ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
conn = psycopg2.connect(
    host="localhost", port=5432, user="eduzim",
    password="eduzim_secret", dbname="auth_db"
)
cur = conn.cursor()

school_id = "11111111-1111-1111-1111-111111111111"

# Delete old users
cur.execute("DELETE FROM user_roles WHERE user_id IN ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid, 'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid)")
cur.execute("DELETE FROM users WHERE id IN ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid, 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid, 'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid)")

users = [
    ("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "admin@test.com", "Admin User", ctx.hash("admin123"), "SchoolAdmin"),
    ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "teacher@test.com", "Teacher User", ctx.hash("teacher123"), "Teacher"),
    ("cccccccc-cccc-cccc-cccc-cccccccccccc", "parent@test.com", "Parent User", ctx.hash("parent123"), "Parent"),
]

for uid, email, name, pw_hash, role_name in users:
    cur.execute(
        "INSERT INTO users (id, email, full_name, password_hash, school_id, is_active) "
        "VALUES (%s, %s, %s, %s, %s, true)",
        (uid, email, name, pw_hash, school_id),
    )
    cur.execute(
        "INSERT INTO user_roles (user_id, role_id) "
        "SELECT %s::uuid, id FROM roles WHERE name = %s",
        (uid, role_name),
    )
    print(f"  OK: {email} / {role_name}")

conn.commit()
cur.close()
conn.close()
print("Done!")
