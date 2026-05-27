"""Test package — sets required-env defaults so config.py loads in test runs."""
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-DO-NOT-USE-IN-PRODUCTION-32chars-min-len-XXXX")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token-DO-NOT-USE-IN-PRODUCTION")
