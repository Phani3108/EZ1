#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# EduZim — Dev Seed Script
# Creates the three local test users (admin / teacher / parent).
# Usage: bash scripts/dev-seed.sh
#
# Password hashes are computed at runtime by the identity container's own
# app.utils.security.hash_password, so they are ALWAYS compatible with the
# running verifier (no stale hand-pasted hashes that match no known password).
# ─────────────────────────────────────────────────────────

set -euo pipefail

DB_USER="${DB_USER:-eduzim}"
DB_NAME="${DB_NAME:-auth_db}"
SCHOOL_ID="11111111-1111-1111-1111-111111111111"

ADMIN_PASS="${ADMIN_PASS:-secureP@ss1}"
PARENT_PASS="${PARENT_PASS:-secureP@ss1}"
TEACHER_PASS="${TEACHER_PASS:-teacher123}"

echo "🌱 EduZim Dev Seed — seeding users..."

hash_pw() {
  docker exec -i eduzim-identity python3 -c \
    "from app.utils.security import hash_password; print(hash_password('$1'))" | tr -d '\r'
}

ADMIN_HASH="$(hash_pw "$ADMIN_PASS")"
PARENT_HASH="$(hash_pw "$PARENT_PASS")"
TEACHER_HASH="$(hash_pw "$TEACHER_PASS")"

echo "  ✅ School: Harare Primary School (${SCHOOL_ID})"

# Hashes are injected as psql variables (-v) and referenced as :'name'.
# This keeps the SQL heredoc single-quoted so the '$' chars inside bcrypt
# hashes are never touched by the shell.
docker exec -i eduzim-postgres psql -U "$DB_USER" -d "$DB_NAME" \
  -v admin_hash="$ADMIN_HASH" \
  -v teacher_hash="$TEACHER_HASH" \
  -v parent_hash="$PARENT_HASH" <<'SQL'
-- Admin user
INSERT INTO users (id, email, full_name, password_hash, school_id, is_active, created_at, updated_at)
VALUES (
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'admin@school.ac.zw',
  'Dev Admin',
  :'admin_hash',
  '11111111-1111-1111-1111-111111111111',
  true, NOW(), NOW()
) ON CONFLICT (id) DO UPDATE SET
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  password_hash = EXCLUDED.password_hash,
  school_id = EXCLUDED.school_id;

-- Teacher user
INSERT INTO users (id, email, full_name, password_hash, school_id, is_active, created_at, updated_at)
VALUES (
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'teacher@eduzim.zw',
  'Dev Teacher',
  :'teacher_hash',
  '11111111-1111-1111-1111-111111111111',
  true, NOW(), NOW()
) ON CONFLICT (id) DO UPDATE SET
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  password_hash = EXCLUDED.password_hash,
  school_id = EXCLUDED.school_id;

-- Parent user
INSERT INTO users (id, email, full_name, password_hash, school_id, is_active, created_at, updated_at)
VALUES (
  'cccccccc-cccc-cccc-cccc-cccccccccccc',
  'parent@school.ac.zw',
  'Dev Parent',
  :'parent_hash',
  '11111111-1111-1111-1111-111111111111',
  true, NOW(), NOW()
) ON CONFLICT (id) DO UPDATE SET
  email = EXCLUDED.email,
  full_name = EXCLUDED.full_name,
  password_hash = EXCLUDED.password_hash,
  school_id = EXCLUDED.school_id;

-- Assign roles
INSERT INTO user_roles (user_id, role_id)
SELECT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid, id FROM roles WHERE name = 'SchoolAdmin'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid, id FROM roles WHERE name = 'Teacher'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id)
SELECT 'cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid, id FROM roles WHERE name = 'Parent'
ON CONFLICT DO NOTHING;
SQL

echo ""
echo "🎉 Dev seed complete!"
echo ""
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│  App              URL                    Credentials         │"
echo "├──────────────────────────────────────────────────────────────┤"
echo "│  Admin Web        http://localhost:3000   admin@school.ac.zw  │"
echo "│                                           ${ADMIN_PASS}"
echo "│  Parent Web       http://localhost:3001   parent@school.ac.zw │"
echo "│                                           ${PARENT_PASS}"
echo "│  Teacher Web      http://localhost:3002   teacher@eduzim.zw   │"
echo "│                                           ${TEACHER_PASS}"
echo "└──────────────────────────────────────────────────────────────┘"
echo ""
echo "Note: demo data (students/classes/etc.) is NOT seeded here."
echo "      Create records via the UI/API, or use a data seeder that targets"
echo "      the consolidated DBs (auth_db, academics_db, fees_db, comms_db,"
echo "      reporting_db). The legacy scripts/rich-seed.py references the"
echo "      pre-consolidation DB names (school_db/student_db/…) and will fail."
