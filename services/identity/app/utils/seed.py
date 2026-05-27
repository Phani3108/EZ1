"""
Seed script for auth-service — Phase 1 roles and permissions.
Run: cd services/auth-service && python -m app.utils.seed
"""
import uuid
from app.database import SessionLocal
from app.models.user import Role, Permission
from app.utils.security import hash_password


PERMISSIONS = [
    {"name": "school:manage", "resource": "school", "action": "manage", "description": "Full school management"},
    {"name": "student:read", "resource": "student", "action": "read", "description": "View student data"},
    {"name": "student:write", "resource": "student", "action": "write", "description": "Create/update students"},
    {"name": "attendance:read", "resource": "attendance", "action": "read", "description": "View attendance"},
    {"name": "attendance:write", "resource": "attendance", "action": "write", "description": "Record attendance"},
    {"name": "fees:read", "resource": "fees", "action": "read", "description": "View fees & invoices"},
    {"name": "fees:write", "resource": "fees", "action": "write", "description": "Manage fees & payments"},
    {"name": "comm:read", "resource": "comm", "action": "read", "description": "View communications"},
    {"name": "comm:write", "resource": "comm", "action": "write", "description": "Send communications"},
]

ROLES = [
    {"name": "SuperAdmin", "description": "Platform-wide superuser"},
    {"name": "SchoolAdmin", "description": "School-level administrator"},
    {"name": "Teacher", "description": "Teacher with classroom access"},
    {"name": "Accountant", "description": "Financial management"},
    {"name": "Parent", "description": "Parent/guardian"},
    {"name": "Student", "description": "Student role"},
]

ROLE_PERMS = {
    "SuperAdmin": [p["name"] for p in PERMISSIONS],
    "SchoolAdmin": [p["name"] for p in PERMISSIONS],
    "Teacher": ["student:read", "attendance:read", "attendance:write", "comm:read", "comm:write"],
    "Accountant": ["student:read", "fees:read", "fees:write"],
    "Parent": ["student:read", "attendance:read", "fees:read", "comm:read"],
    "Student": ["attendance:read", "fees:read", "comm:read"],
}


def seed():
    db = SessionLocal()
    try:
        perm_map = {}
        for p in PERMISSIONS:
            existing = db.query(Permission).filter(Permission.name == p["name"]).first()
            if not existing:
                obj = Permission(id=uuid.uuid4(), **p)
                db.add(obj)
                db.flush()
                perm_map[obj.name] = obj
                print(f"  ✅ Permission: {obj.name}")
            else:
                perm_map[existing.name] = existing

        role_map = {}
        for r in ROLES:
            existing = db.query(Role).filter(Role.name == r["name"]).first()
            if not existing:
                obj = Role(id=uuid.uuid4(), **r)
                db.add(obj)
                db.flush()
                role_map[obj.name] = obj
                print(f"  ✅ Role: {obj.name}")
            else:
                role_map[existing.name] = existing

        for role_name, perm_names in ROLE_PERMS.items():
            role = role_map.get(role_name)
            if not role:
                continue
            for pn in perm_names:
                perm = perm_map.get(pn)
                if perm and perm not in role.permissions:
                    role.permissions.append(perm)
            print(f"  🔗 {role_name} ← {len(perm_names)} permissions")

        db.commit()
        print("\n🎉 Seed complete!")
    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
