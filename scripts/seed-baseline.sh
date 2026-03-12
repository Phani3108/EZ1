#!/usr/bin/env bash
# Seed baseline roles and permissions into auth_db via Docker exec

DB_NAME="auth_db"
DB_USER="eduzim"

echo "🌱 Seeding Baseline Roles and Permissions via Docker..."

docker exec -i eduzim-postgres psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
-- 1. Roles (Valid UUIDs)
INSERT INTO roles (id, name, description) VALUES 
  ('11111111-1111-1111-1111-111111111111', 'SchoolAdmin', 'Full administrative access and reporting.'),
  ('22222222-2222-2222-2222-222222222222', 'Teacher', 'Teaching and grading permissions.'),
  ('33333333-3333-3333-3333-333333333333', 'Parent', 'View child progress and financials.'),
  ('44444444-4444-4444-4444-444444444444', 'Student', 'Student portal access.')
ON CONFLICT (name) DO NOTHING;

-- 2. Permissions (Valid UUIDs)
INSERT INTO permissions (id, name, description, resource, action) VALUES 
  ('a1111111-1111-1111-1111-111111111111', 'school:manage', 'Manage school settings', 'school', 'manage'),
  ('b2222222-2222-2222-2222-222222222222', 'student:write', 'Manage students', 'student', 'write'),
  ('c3333333-3333-3333-3333-333333333333', 'student:read', 'View students', 'student', 'read'),
  ('d4444444-4444-4444-4444-444444444444', 'attendance:write', 'Mark attendance', 'attendance', 'write'),
  ('e5555555-5555-5555-5555-555555555555', 'attendance:read', 'View attendance', 'attendance', 'read'),
  ('f6666666-6666-6666-6666-666666666666', 'fees:write', 'Manage fees', 'fees', 'write'),
  ('12222222-2222-2222-2222-222222222222', 'fees:read', 'View fees', 'fees', 'read'),
  ('23333333-3333-3333-3333-333333333333', 'comm:write', 'Send comms', 'comm', 'write'),
  ('34444444-4444-4444-4444-444444444444', 'comm:read', 'Read comms', 'comm', 'read'),
  ('45555555-5555-5555-5555-555555555555', 'report:read', 'View reports', 'report', 'read'),
  ('56666666-6666-6666-6666-666666666666', 'report:admin', 'Admin reports', 'report', 'admin'),
  ('67777777-7777-7777-7777-777777777777', 'assessment:write', 'Grade assessments', 'assessment', 'write'),
  ('78888888-8888-8888-8888-888888888888', 'assessment:read', 'View assessments', 'assessment', 'read')
ON CONFLICT (name) DO NOTHING;

-- 3. Associate Permissions to Roles
-- SchoolAdmin gets everything
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'SchoolAdmin'
ON CONFLICT DO NOTHING;

-- Teacher
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'Teacher' 
AND p.name IN ('student:read', 'attendance:write', 'attendance:read', 'report:read', 'assessment:write', 'assessment:read', 'comm:read')
ON CONFLICT DO NOTHING;

-- Parent
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'Parent' 
AND p.name IN ('student:read', 'report:read', 'fees:read', 'comm:read', 'assessment:read')
ON CONFLICT DO NOTHING;
SQL

echo "✅ Baseline roles and permissions seeded."
