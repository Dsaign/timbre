"""Feedback: one vote per (visitor hash, normalized Description, Song), latest wins.

Nothing stored identifies the visitor: the IP is kept only as a salted HMAC, and that
hash is cleared after 7 days while the vote stays.
"""

import asyncio
import hashlib
import hmac
import logging
import unicodedata
from ipaddress import IPv4Address, IPv6Address
from typing import Literal
from uuid import UUID

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger("timbre.feedback")

Vote = Literal["up", "down"]


def normalize(description: str) -> str:
    """Unicode NFC, trimmed, whitespace collapsed, lowercased."""
    return " ".join(unicodedata.normalize("NFC", description).split()).lower()


def hash_ip(ip: IPv4Address | IPv6Address, salt: bytes) -> str:
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped  # "::ffff:1.2.3.4" is the same visitor as "1.2.3.4"
    return hmac.new(salt, ip.packed, hashlib.sha256).hexdigest()


async def as_visitor(conn: AsyncConnection, visitor: str) -> None:
    """For this transaction, RLS lets api_search touch only this visitor's votes."""
    await conn.execute("SELECT set_config('app.visitor_hash', %s, true)", (visitor,))


async def record(
    pool: AsyncConnectionPool,
    visitor: str,
    description: str,
    song_id: UUID,
    vote: Vote | None,
) -> bool:
    """Store, switch or (None) withdraw a vote. False: no such Song in the Catalog."""
    async with pool.connection() as conn:
        await as_visitor(conn, visitor)
        key = (visitor, normalize(description), song_id)
        if vote is None:
            await conn.execute(
                "DELETE FROM feedback.votes"
                " WHERE visitor_hash = %s AND description = %s AND song_id = %s",
                key,
            )
            return True
        cur = await conn.execute(
            "INSERT INTO feedback.votes (visitor_hash, description, song_id, vote)"
            " SELECT %s, %s, id, %s FROM catalog.songs WHERE id = %s"
            " ON CONFLICT (visitor_hash, description, song_id)"
            " DO UPDATE SET vote = excluded.vote, updated_at = now()",
            (visitor, key[1], vote, song_id),
        )
        return cur.rowcount == 1


async def forget_old_hashes(pool: AsyncConnectionPool) -> int:
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT feedback.forget_old_visitor_hashes()")
        row = await cur.fetchone()
        return int(row[0]) if row else 0


async def forget_old_hashes_daily(pool: AsyncConnectionPool) -> None:
    while True:
        try:
            forgotten = await forget_old_hashes(pool)
            log.info("visitor hash expiry: %d votes anonymized", forgotten)
        except Exception:
            log.exception("visitor hash expiry failed")
        await asyncio.sleep(24 * 60 * 60)
