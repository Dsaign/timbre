"""One-off: write the seed Catalog to src/timbre_back/seed.json.

Run from back/: `METABRAINZ_CONTACT=<email or URL> uv run python scripts/fetch_seed.py`.
Takes a few minutes.

Candidates are ListenBrainz's sitewide all-time top recordings, at most PER_ARTIST
per artist. (The per-artist popularity endpoints now need a ListenBrainz token; the
sitewide stats do not.) A Song is kept only if it has an ISRC and AcousticBrainz
high-level data. CC0 fields only (ADR 0002): no MusicBrainz tags or genres.
"""

import asyncio
import json
from pathlib import Path

import httpx

from timbre_back.metabrainz import (
    LISTENBRAINZ_API,
    METADATA_BATCH,
    STATS_PAGE,
    Song,
    client,
    fetch_high_level,
    fetch_json,
    recordings_metadata,
    to_song,
)

TARGET = 200
PER_ARTIST = 3
OUT = Path(__file__).parent.parent / "src" / "timbre_back" / "seed.json"


async def fetch_songs(http: httpx.AsyncClient) -> list[Song]:
    songs: list[Song] = []
    per_artist: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    stats_pages = range(0, 5 * STATS_PAGE, STATS_PAGE)
    for offset in stats_pages:
        page = await fetch_json(
            http,
            f"{LISTENBRAINZ_API}/stats/sitewide/recordings",
            params={
                "range": "all_time",
                "count": STATS_PAGE,
                "offset": offset,
            },
        )
        candidates = []
        for candidate in page["payload"]["recordings"]:
            key = (
                candidate["artist_name"].casefold(),
                candidate["track_name"].casefold(),
            )
            if candidate.get("recording_mbid") and key not in seen:
                seen.add(key)
                candidates.append(candidate)
        acousticbrainz = await fetch_high_level(
            http, [c["recording_mbid"] for c in candidates]
        )
        analysed = [
            c
            for c in candidates
            if c["recording_mbid"] in acousticbrainz
            and per_artist.get(c["artist_name"], 0) < PER_ARTIST
        ]
        for i in range(0, len(analysed), METADATA_BATCH):
            batch = analysed[i : i + METADATA_BATCH]
            recordings = await recordings_metadata(
                http, [c["recording_mbid"] for c in batch]
            )
            for candidate in batch:
                mbid = candidate["recording_mbid"]
                recording = recordings.get(mbid, {}).get("recording", {})
                artist = candidate["artist_name"]
                full = per_artist.get(artist, 0) >= PER_ARTIST
                if full or not recording.get("isrcs"):
                    continue
                per_artist[artist] = per_artist.get(artist, 0) + 1
                songs.append(
                    to_song(
                        mbid,
                        candidate["track_name"],
                        artist,
                        candidate["listen_count"],
                        acousticbrainz[mbid],
                        recording,
                    )
                )
        print(f"offset {offset}: {len(songs)} Songs so far", flush=True)
        if len(songs) >= TARGET:
            break
    return songs[:TARGET]


async def main() -> None:
    async with client() as http:
        songs = await fetch_songs(http)
    OUT.write_text(json.dumps(songs, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {len(songs)} Songs to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
