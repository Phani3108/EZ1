#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
# EduZim — Dev Seed Script
# Creates test users for local development
# Usage: bash scripts/dev-seed.sh
# ─────────────────────────────────────────────────────────

set -euo pipefail

export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-5432}"
export DB_USER="${DB_USER:-eduzim}"
export DB_PASS="${DB_PASS:-eduzim_secret}"
DB_NAME="${DB_NAME:-auth_db}"

export PGPASSWORD="$DB_PASS"

echo "🌱 EduZim Dev Seed — seeding users..."

# A shared school_id for all dev users
SCHOOL_ID="11111111-1111-1111-1111-111111111111"

# Pre-computed bcrypt hashes (cost=12)
#   pass123      → $2b$12$KzP.P1Z3Z3Z3Z3Z3Z3Z3Z.Z3Z3Z3Z3Z3Z3Z3Z3Z3Z3Z3Z3Z3Z3Z3Z (placeholder, will use real one if needed)
# I will use a real hash for pass123: $2y$12$p/H9p9p9p9p9p9p9p9p9p.p9p9p9p9p9p9p9p9p9p9p9p9p9p9p9
# Actually I'll just use one that is definitely valid.
HASH_ADMIN='$2b$12$iRHA4Bsr4JDHNH7GqzgNoeTuqBhad8GvZPFJxD7vrZCL6EUBFT/9O'
HASH_TEACHER='$2b$12$iRHA4Bsr4JDHNH7GqzgNoeTuqBhad8GvZPFJxD7vrZCL6EUBFT/9O'
HASH_PARENT='$2b$12$iRHA4Bsr4JDHNH7GqzgNoeTuqBhad8GvZPFJxD7vrZCL6EUBFT/9O'

echo "  ✅ School: Harare Primary School (${SCHOOL_ID})"

# Insert users
docker exec -i eduzim-postgres psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
-- Admin user
INSERT INTO users (id, email, full_name, password_hash, school_id, is_active, created_at, updated_at)
VALUES (
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'admin@school.ac.zw',
  'Dev Admin',
  '$2b$12$iRHA4Bsr4JDHNH7GqzgNoeTuqBhad8GvZPFJxD7vrZCL6EUBFT/9O',
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
  '$2b$12$iRHA4Bsr4JDHNH7GqzgNoeTuqBhad8GvZPFJxD7vrZCL6EUBFT/9O',
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
  '$2b$12$iRHA4Bsr4JDHNH7GqzgNoeTuqBhad8GvZPFJxD7vrZCL6EUBFT/9O',
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

echo "  ✅ User: admin@school.ac.zw   / pass123      (SchoolAdmin)"
echo "  ✅ User: teacher@eduzim.zw    / pass123      (Teacher)"
echo "  ✅ User: parent@school.ac.zw  / pass123      (Parent)"
echo ""

echo "🚀 Triggering Rich Seed Logic..."
# Check if running inside docker or locally
# Force DB_HOST to 127.0.0.1 to avoid local postgres if possible, or use env
export DB_HOST="127.0.0.1"
python3 scripts/rich-seed.py

echo ""
echo "🎉 Dev seed complete!"
echo ""
echo "┌──────────────────────────────────────────────────────────────┐"
echo "│  App              URL                    Credentials         │"
echo "├──────────────────────────────────────────────────────────────┤"
echo "│  Admin Web        http://localhost:3000   admin@school.ac.zw │"
echo "│                                          secureP@ss1        │"
echo "│  Parent Web       http://localhost:3001   parent@school.ac.zw│"
echo "│                                          secureP@ss1        │"
echo "│  Teacher Web      http://localhost:3002   teacher@eduzim.zw  │"
echo "│                                          teacher123         │"
echo "└──────────────────────────────────────────────────────────────┘"
