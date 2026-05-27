"""Sentinel-aware Redis client factory (INFRA-006 / Phase 5).

The single-node Redis runtime accepts `redis://[:password@]host:port/db`
and `redis.from_url(...)` handles it natively. The Sentinel HA topology
needs a different call shape (`redis.sentinel.Sentinel([(host, port)...],
password=...).master_for("mymaster")`), but we don't want every callsite
to branch on the topology.

This factory accepts EITHER URL form and returns a usable redis.Redis
client. Callers do:

    from eduzim_shared.redis_client import from_url
    client = from_url(settings.REDIS_URL)

Sentinel-URL shape (extends the standard redis URL with a `?master=NAME`
query and accepts multiple host:port pairs comma-separated):

    redis+sentinel://[:password@]host1:26379,host2:26379,host3:26379/N?master=mymaster

The function performs sentinel discovery once at client-build time. The
Sentinel itself handles re-discovery on master failover — applications
don't need to reconnect or re-resolve manually.
"""
from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlsplit


logger = logging.getLogger(__name__)


def from_url(url: str, *, decode_responses: bool = True, socket_timeout: Optional[float] = 5.0):
    """Build a redis client from a URL.

    Supports:
      * `redis://...`           → plain `redis.from_url` (single-node)
      * `rediss://...`          → plain `redis.from_url` (TLS single-node)
      * `redis+sentinel://...`  → Sentinel-aware (HA)
    """
    if url.startswith("redis+sentinel://"):
        return _sentinel_client(
            url,
            decode_responses=decode_responses,
            socket_timeout=socket_timeout,
        )

    import redis as _redis
    return _redis.from_url(
        url,
        decode_responses=decode_responses,
        socket_timeout=socket_timeout,
    )


# ───────────── internal: sentinel parsing ─────────────


_SCHEME_RE = re.compile(r"^redis\+sentinel://", re.IGNORECASE)


def _sentinel_client(url: str, *, decode_responses: bool, socket_timeout: Optional[float]):
    """Parse a `redis+sentinel://` URL and return a master client."""
    # Strip our custom scheme prefix; urlsplit treats `redis://` as known.
    # We restore the standard scheme so urlsplit handles password / db / etc.
    canonical = _SCHEME_RE.sub("redis://", url)
    parts = urlsplit(canonical)

    # `parts.netloc` may contain `:password@h1:26379,h2:26379,h3:26379`.
    # `urlsplit` keeps the password in parts.password and treats the
    # host portion as a single string up to the first ':' — but with
    # comma-separated hosts it puts the whole thing in `hostname`. So
    # we re-parse `parts.netloc` manually to extract every host:port.
    netloc = parts.netloc
    password = parts.password
    if "@" in netloc:
        _, hosts_part = netloc.rsplit("@", 1)
    else:
        hosts_part = netloc

    sentinel_pairs: list[tuple[str, int]] = []
    for entry in hosts_part.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            host, port = entry.rsplit(":", 1)
            sentinel_pairs.append((host, int(port)))
        else:
            # Default sentinel port if not specified
            sentinel_pairs.append((entry, 26379))

    if not sentinel_pairs:
        raise ValueError(f"redis+sentinel URL has no sentinel hosts: {url!r}")

    # `parts.path` is `/N` where N is the DB index. Empty → 0.
    db = 0
    if parts.path and parts.path.lstrip("/"):
        try:
            db = int(parts.path.lstrip("/"))
        except ValueError as exc:
            raise ValueError(f"redis+sentinel URL has non-int db: {parts.path!r}") from exc

    query = parse_qs(parts.query or "")
    master_name = (query.get("master") or query.get("master_name") or ["mymaster"])[0]

    from redis.sentinel import Sentinel as _Sentinel

    sentinel = _Sentinel(
        sentinel_pairs,
        socket_timeout=socket_timeout,
        password=password,        # for sentinel auth itself
        sentinel_kwargs={"password": password} if password else None,
    )
    logger.info(
        "redis_sentinel_init",
        extra={
            "master_name": master_name,
            "sentinel_count": len(sentinel_pairs),
            "db": db,
        },
    )
    # `master_for` returns a redis.Redis-compatible object that auto-
    # rediscovers the master on failover.
    return sentinel.master_for(
        master_name,
        socket_timeout=socket_timeout,
        password=password,
        db=db,
        decode_responses=decode_responses,
    )
