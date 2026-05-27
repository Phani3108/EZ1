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
  ('44444444-4444-4444-4444-444444444444', 'Student', 'Student portal access.'),
  -- Phase 14 / DEC-013: Ministry is viewer + auditor only. NO operational
  -- verbs anywhere in the UI; the role grants ministry:read only.
  ('55555555-5555-5555-5555-555555555555', 'Ministry', 'Ministry / MoPSE — cross-school aggregation read-only.'),
  -- Phase 15 / ADR 021: narrow write carve-out for Ministry users who
  -- need to provision schools. ADDITIVE — meant to be held alongside
  -- the `Ministry` role (Ministry+Provisioner). Grants only
  -- `school:create` + `invite:write`. Never grants operational verbs.
  ('66666666-6666-6666-6666-666666666666', 'Provisioner', 'Ministry add-on: create schools + invite first SchoolAdmin.'),
  -- Phase 15 / ADR 021: internal EduZim Operations super-admin. Holds
  -- school:create + invite:write + a cross-tenant read. Reserved for
  -- the EduZim platform team.
  ('77777777-7777-7777-7777-777777777777', 'EduZimOps', 'EduZim Operations — internal cross-tenant operator (school onboarding).')
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
  ('78888888-8888-8888-8888-888888888888', 'assessment:read', 'View assessments', 'assessment', 'read'),
  -- Phase 14 / DEC-013: Ministry is read-only cross-school aggregation.
  -- Only ministry:read is granted; no write/admin verbs ever map to Ministry.
  ('89999999-9999-9999-9999-999999999999', 'ministry:read', 'Read cross-school aggregations (Ministry / MoPSE)', 'ministry', 'read'),
  -- Phase 15 / ADR 021: narrow write permissions for the onboarding
  -- carve-out. school:create allows POST /schools; invite:write allows
  -- POST /invitations. student:draft allows Teachers to submit
  -- StudentDraft rows (Admin still approves before they go live).
  ('9aaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'school:create', 'Create a new school (onboarding)', 'school', 'create'),
  ('9bbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'invite:write', 'Create + dispatch invitations (onboarding)', 'invite', 'write'),
  ('9ccccccc-cccc-cccc-cccc-cccccccccccc', 'student:draft', 'Teacher: submit a student draft for admin approval', 'student', 'draft')
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

-- Ministry (Phase 14 / DEC-013): ONLY ministry:read. No operational verbs.
-- The gateway RBAC layer enforces this; the route layer also asserts the
-- 'Ministry' role explicitly as defence-in-depth.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'Ministry'
AND p.name = 'ministry:read'
ON CONFLICT DO NOTHING;

-- Provisioner (Phase 15 / ADR 021): narrow add-on for Ministry users
-- who need to onboard schools. school:create + invite:write only.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'Provisioner'
AND p.name IN ('school:create', 'invite:write')
ON CONFLICT DO NOTHING;

-- EduZimOps (Phase 15 / ADR 021): internal cross-tenant operator.
-- school:create + invite:write + ministry:read (read view of every
-- tenant). Reserved for the EduZim platform team.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'EduZimOps'
AND p.name IN ('school:create', 'invite:write', 'ministry:read')
ON CONFLICT DO NOTHING;

-- Teacher (Phase 15): grant student:draft so teachers can submit
-- pending student rows that an Admin reviews before publishing.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'Teacher'
AND p.name = 'student:draft'
ON CONFLICT DO NOTHING;

-- SchoolAdmin (Phase 15): inherit invite:write so admins can invite
-- teachers, parents, and other admins from the setup wizard.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = 'SchoolAdmin'
AND p.name = 'invite:write'
ON CONFLICT DO NOTHING;
SQL

echo "✅ Baseline roles and permissions seeded."
