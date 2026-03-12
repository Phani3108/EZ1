import os

services = [
    "auth-service", "school-service", "student-service", "attendance-service",
    "fees-service", "communication-service", "reporting-service",
    "assessment-service", "api-gateway"
]

def update_dockerfile(svc):
    path = f"services/{svc}/Dockerfile"
    if not os.path.exists(path):
        print(f"Skipping {svc}, path not found")
        return

    with open(path, "r") as f:
        lines = f.readlines()

    new_lines = []
    has_shared = False
    for line in lines:
        if "COPY requirements.txt" in line:
            new_lines.append(f"COPY ./services/{svc}/requirements.txt .\n")
        elif "COPY ../../shared /shared" in line or "COPY ./shared /shared" in line:
            if not has_shared:
                new_lines.append("COPY ./shared /shared\n")
                has_shared = True
        elif "RUN pip install -e /shared" in line:
            new_lines.append("RUN pip install -e /shared\n")
        elif 'CMD ["sh", "-c", "alembic upgrade head && ' in line:
            # Remove alembic for non-auth services
            if svc != "auth-service":
                new_lines.append(line.replace("alembic upgrade head && ", ""))
            else:
                new_lines.append(line)
        elif "COPY . ." in line or f"COPY ./services/{svc} ." in line:
            # For assessment-service, we might need a slightly different structure if it was already modified
            new_lines.append(f"COPY ./services/{svc} .\n")
        elif "COPY ./services/" in line and svc not in line:
             # Fix the copy paste error from my previous manual edit
             new_lines.append(f"COPY ./services/{svc} .\n")
        else:
            new_lines.append(line)
            
    # Final check for shared if missing (except gateway maybe)
    if svc != "api-gateway" and not has_shared:
        # Insert before requirements or app code
        idx = 0
        for i, l in enumerate(new_lines):
            if "COPY" in l:
                idx = i
                break
        new_lines.insert(idx, "COPY ./shared /shared\nRUN pip install -e /shared\n\n")

    with open(path, "w") as f:
        f.writelines(new_lines)
    print(f"Updated {path}")

for svc in services:
    update_dockerfile(svc)
