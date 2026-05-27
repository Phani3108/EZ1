"""Uvicorn launcher that auto-wires mTLS when enabled.

Usage from a service Dockerfile CMD:

    CMD ["python", "-m", "eduzim_shared.serve", "app.main:app"]

This wrapper:
  * Reads PORT (default 8000)
  * Reads EDUZIM_TLS_* env and configures uvicorn with TLS if enabled
  * Falls back to plain HTTP otherwise
  * Forwards everything else (host, workers, etc.) to uvicorn

The point: services don't need to know whether they're running in
single-node or HA mode. The compose env decides; the Dockerfile CMD
stays constant.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="EduZim uvicorn launcher with mTLS auto-config",
    )
    parser.add_argument("app", help="Uvicorn app spec, e.g. 'app.main:app'")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    import uvicorn
    from eduzim_shared import mtls

    kwargs = {
        "host": args.host,
        "port": args.port,
        "workers": args.workers,
        "reload": args.reload,
    }
    # mtls.uvicorn_kwargs() returns {} when EDUZIM_TLS_ENABLED is false.
    kwargs.update(mtls.uvicorn_kwargs())

    if "ssl_certfile" in kwargs:
        logging.info("[serve] mTLS enabled — binding %s:%d with cert %s",
                     args.host, args.port, kwargs["ssl_certfile"])
    else:
        logging.info("[serve] mTLS disabled — binding %s:%d (HTTP)",
                     args.host, args.port)

    uvicorn.run(args.app, **kwargs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
