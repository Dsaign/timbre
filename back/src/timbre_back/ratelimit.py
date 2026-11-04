"""Rate limits per visitor hash, counted in Postgres (migration 20261103200000)."""

import asyncio
import logging
from datetime import timedelta

from psycopg_pool import AsyncConnectionPool

log = logging.getLogger("timbre.ratelimit")


async def over_limit(
    pool: AsyncConnectionPool, visitor: str, action: str, per: timedelta, limit: int
) -> bool:
    """Counts this hit; True when the visitor made more than `limit` within `per`."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT ratelimit.hit(%s, %s, %s)", (visitor, action, per)
        )
        row = await cur.fetchone()
    return bool(row and row[0] > limit)


async def forget_old_hits(pool: AsyncConnectionPool) -> int:
    """Counters hold visitor hashes, so they are deleted a day after their window."""
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT ratelimit.forget_old_hits()")
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def forget_old_hits_daily(pool: AsyncConnectionPool) -> None:
    while True:
        try:
            log.info(
                "rate-limit expiry: %d counters deleted", await forget_old_hits(pool)
            )
        except Exception:
            log.exception("rate-limit expiry failed")
        await asyncio.sleep(24 * 60 * 60)
