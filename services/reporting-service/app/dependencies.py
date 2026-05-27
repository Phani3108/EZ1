"""Auth dependencies — vestigial at PH2-11/PH3.

The reporting-service container is a Kafka consumer with no HTTP surface
besides `/health` (which doesn't need auth). This module is kept on disk
only because legacy code occasionally imports `get_current_user` for
side-effects; it raises if anyone actually invokes it.
"""
from fastapi import HTTPException


def get_current_user(*_args, **_kwargs):
    raise HTTPException(
        status_code=410,
        detail="reporting-service HTTP auth was removed at PH2-11. "
               "This consumer container has no authenticated routes.",
    )


def get_school_id(*_args, **_kwargs):
    raise HTTPException(
        status_code=410,
        detail="reporting-service HTTP auth was removed at PH2-11.",
    )
