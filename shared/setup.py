from setuptools import setup, find_packages

setup(
    name="eduzim-shared",
    version="1.0.0",
    description="Shared libraries for EduZim microservices",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "confluent-kafka>=2.3.0",
        "pydantic>=2.0.0",
        "fastapi>=0.109.0",
        # INFRA-007 / Phase 6 — Prometheus exposition. Required because
        # app_factory.create_app() installs the metrics middleware by
        # default.
        "prometheus-client>=0.20.0",
    ],
    extras_require={
        # INFRA-008 / Phase 6 — OpenTelemetry. Optional install: the
        # `tracing.install()` call is a no-op when these packages
        # aren't present (logs a warning + continues). Production
        # services opt in via `pip install eduzim-shared[tracing]`.
        "tracing": [
            "opentelemetry-api>=1.27.0",
            "opentelemetry-sdk>=1.27.0",
            "opentelemetry-exporter-otlp-proto-grpc>=1.27.0",
            "opentelemetry-instrumentation-fastapi>=0.48b0",
            "opentelemetry-instrumentation-httpx>=0.48b0",
            "opentelemetry-instrumentation-sqlalchemy>=0.48b0",
            "opentelemetry-instrumentation-logging>=0.48b0",
        ],
        # INFRA-010 / Phase 6 — Sentry SDK. Optional for the same reason.
        "sentry": [
            "sentry-sdk[fastapi]>=2.0.0",
        ],
        # INFRA-006 / Phase 5 — Redis client used by the sentinel-aware
        # factory in eduzim_shared.redis_client. Optional because not
        # every service touches Redis.
        "redis": [
            "redis>=5.0.0",
        ],
    },
)
