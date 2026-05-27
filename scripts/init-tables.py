#!/usr/bin/env python3
import sys
import os
import importlib

# Add shared lib and services to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "shared"))

SERVICES = {
    # PH2-2: auth-service renamed to identity; DB name kept as auth_db
    # until PH2 collapses identity_db / academics_db etc.
    "auth_db": "services/identity",
    "school_db": "services/school-service",
    # PH2-6: academics runs alongside school-service; uses academics_db
    # so the burn-in doesn't share state with school_db.
    "academics_db": "services/academics",
    "student_db": "services/student-service",
    "attendance_db": "services/attendance-service",
    # PH2-3: fees-service renamed to finance; DB name kept as fees_db.
    "fees_db": "services/finance",
    # PH2-4: communication-service renamed to communications; DB name kept.
    "comms_db": "services/communications",
    "reporting_db": "services/reporting-service",
    "assessment_db": "services/assessment-service",
}

def init_service_db(db_name, service_path):
    print(f"🛠️ Initializing {db_name} via {service_path}...")
    service_abs_path = os.path.join(ROOT_DIR, service_path)
    sys.path.insert(0, service_abs_path)
    
    try:
        # We need to import the Base and all models so they are registered
        from app.database import Base, engine
        
        # Import models based on service
        if db_name == "auth_db":
            import app.models.user
        elif db_name == "school_db":
            import app.models.school
        elif db_name == "student_db":
            import app.models.student
        elif db_name == "attendance_db":
            import app.models.attendance
        elif db_name == "fees_db":
            import app.models.fees
        elif db_name == "comms_db":
            import app.models.communication
        elif db_name == "reporting_db":
            import app.models.projections
        elif db_name == "assessment_db":
            import app.models.assessment
            
        print(f"  Tables found in metadata: {list(Base.metadata.tables.keys())}")
        if not Base.metadata.tables:
            print("  ⚠️ Warning: No tables found in metadata! Check model imports.")
            
        Base.metadata.create_all(bind=engine)
        print(f"  ✅ {db_name} tables created.")
    except Exception as e:
        print(f"  ❌ Failed to initialize {db_name}: {e}")
    finally:
        if service_abs_path in sys.path:
            sys.path.remove(service_abs_path)
        # Clear 'app' and its sub-modules from sys.modules to allow reloading for next service
        to_delete = [m for m in sys.modules if m == 'app' or m.startswith('app.')]
        for m in to_delete:
            del sys.modules[m]

if __name__ == "__main__":
    # Ensure DATABASE_URL is set or derived for each service
    # The services expect DATABASE_URL in environment
    # For this script, we'll temporarily point them to localhost if not set
    
    base_url = os.environ.get("DB_BASE_URL", "postgresql://eduzim:eduzim_secret@localhost:5432")
    
    for db, path in SERVICES.items():
        os.environ["DATABASE_URL"] = f"{base_url}/{db}"
        init_service_db(db, path)
