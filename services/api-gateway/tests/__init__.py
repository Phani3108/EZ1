"""Test package — sets required-env defaults so config.py loads in test runs.

Production deployments MUST provide real values via .env / Secrets Manager
(BUG-003). These setdefaults are *only* in effect when running the test
suite and contain obviously-test values to ensure no accidental promotion
to production.
"""
import os

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-DO-NOT-USE-IN-PRODUCTION-32chars-min-len-XXXX",
)
