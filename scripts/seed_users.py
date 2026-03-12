#!/usr/bin/env python3
"""Create dev users in auth_db."""
import psycopg2
from passlib.context import CryptContext

ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
conn = psycopg2.connect(
    host="localhost", port=5432, user="eduzim",
    password="eduzim_secret", dbname="auth_db"
)
cur = conn.cursor()

school_id = "11111111-1111-1111-1111-111111111111"
users = [
    ("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "admin@school.ac.zw", "Dev Admin", ctx.hash("secureP@ss1"), "SchoolAdmin"),
    ("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "teacher@eduzim.zw", "Dev Teacher", ctx.hash("teacher123"), "Teacher"),
    ("cccccccc-cccc-cccc-cccc-cccccccccccc", "parent@school.ac.zw", "Dev Parent", ctx.hash("secureP@ss1"), "Parent"),
]

for uid, email, name, pw_hash, role_name in users:
    cur.execute(
        "INSERT INTO users (id, email, full_name, password_hash, school_id, is_active) "
        "VALUES (%s, %s, %s, %s, %s, true) ON CONFLICT DO NOTHING",
        (uid, email, name, pw_hash, school_id),
    )
    cur.execute(
        "INSERT INTO user_roles (user_id, role_id) "
        "SELECT %s::uuid, id FROM roles WHERE name = %s "
        "ON CONFLICT DO NOTHING",
        (uid, role_name),
    )
    print(f"  OK: {email} ({role_name})")

conn.commit()
cur.close()
conn.close()
print("Done!")
