# Dedicated migrations container (BUG-008 / INFRA-008 / Phase 4).
#
# Runs `alembic upgrade head` for every service in turn against the
# right DATABASE_URL, then exits cleanly. Service containers
# `depends_on: migrations: condition: service_completed_successfully`
# so they only boot once the schema is up-to-date.
#
# Why a dedicated container?
#   - The pre-Phase-4 pattern (each service ran `alembic upgrade head &&
#     uvicorn` in its CMD) had a race on cold startup: 6 containers all
#     trying to acquire the alembic migration lock simultaneously,
#     hitting Postgres before pgbouncer was ready, occasionally
#     deadlocking. Pulling it out into a one-shot container removes that
#     race AND makes prod deploys explicit ("the migrations step has its
#     own status to monitor / roll back").
#
# How it works:
#   - This image bundles every service's alembic tree (academics,
#     finance, communications, reporting-service, identity).
#   - `run.sh` iterates through them, setting DATABASE_URL per service.
#   - Exits with the worst exit code seen so compose / k8s can fail-fast.
FROM python:3.11-slim

WORKDIR /migrations

# Postgres client lib for alembic's psycopg2 driver
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# All services use a fairly common requirements set; install alembic +
# psycopg2 + sqlalchemy globally, then pick up service-specific
# requirements when the service's code is copied in.
RUN pip install --no-cache-dir \
        alembic==1.13.1 \
        sqlalchemy==2.0.30 \
        psycopg2-binary==2.9.9 \
        pydantic==2.7.4 \
        pydantic-settings==2.2.1

# Bring in shared so service env.py imports work.
COPY ./shared /shared
RUN pip install -e /shared

# Bring in every service's alembic tree + models package. The script
# walks /migrations/services/* at runtime.
COPY ./services/academics /migrations/services/academics
COPY ./services/finance /migrations/services/finance
COPY ./services/communications /migrations/services/communications
COPY ./services/reporting-service /migrations/services/reporting-service
COPY ./services/identity /migrations/services/identity

# The per-service requirements files cover any odd model deps not in the
# global install above (e.g. enum types, custom Column subclasses). We
# install each in a best-effort loop — failures here are non-fatal
# because the alembic env.py imports surface the real issue.
RUN for svc in academics finance communications reporting-service identity; do \
        if [ -f "/migrations/services/$svc/requirements.txt" ]; then \
            pip install --no-cache-dir -r "/migrations/services/$svc/requirements.txt" || true; \
        fi; \
    done

COPY ./services/migrations/run.sh /migrations/run.sh
RUN chmod +x /migrations/run.sh

# Default env — overridden by compose at runtime.
ENV DB_USER=eduzim \
    DB_PASSWORD=eduzim_secret \
    DB_HOST=postgres \
    DB_PORT=5432

CMD ["/migrations/run.sh"]
