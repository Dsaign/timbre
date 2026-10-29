"""One-off: write the seed Catalog to src/timbre_back/seed.json.

Run from back/: `METABRAINZ_CONTACT=<email or URL> uv run python scripts/fetch_seed.py`.
Takes a few minutes.

Candidates are ListenBrainz's sitewide all-time top recordings, at most PER_ARTIST
per artist. (The per-artist popularity endpoints now need a ListenBrainz token; the
sitewide stats do not.) A Song is kept only if it has an ISRC and AcousticBrainz
high-level data. CC0 fields only (ADR 0002): no MusicBrainz tags or genres.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

TARGET = 200
PER_ARTIST = 3
OUT = Path(__file__).parent.parent / "src" / "timbre_back" / "seed.json"
LB = "https://api.listenbrainz.org/1"
AB = "https://acousticbrainz.org/api/v1"

# MetaBrainz asks for a contact (email or URL) in the User-Agent.
client = httpx.Client(
    headers={"User-Agent": f"timbre-seed/0.1 ( {os.environ['METABRAINZ_CONTACT']} )"},
    timeout=60,
)


def get(url: str, **params: str) -> Any:
    """GET at most once per second (MetaBrainz asks for no more than 1 call/s)."""
    time.sleep(1.1)
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def acousticbrainz(mbids: list[str]) -> dict[str, dict[str, dict[str, float]]]:
    """High-level class probabilities per recording, 25 recordings per call."""
    found = {}
    for i in range(0, len(mbids), 25):
        data = get(f"{AB}/high-level", recording_ids=";".join(mbids[i : i + 25]))
        for mbid, docs in data.items():
            if mbid == "mbid_mapping":
                continue
            highlevel = docs["0"]["highlevel"]
            found[mbid] = {
                name: {label: round(p, 3) for label, p in c["all"].items()}
                for name, c in highlevel.items()
            }
    return found


def main() -> None:
    songs: list[dict[str, Any]] = []
    per_artist: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()
    for offset in range(0, 5000, 1000):
        page = get(
            f"{LB}/stats/sitewide/recordings",
            range="all_time",
            count="1000",
            offset=str(offset),
        )
        candidates = []
        for r in page["payload"]["recordings"]:
            key = (r["artist_name"].casefold(), r["track_name"].casefold())
            if r.get("recording_mbid") and key not in seen:
                seen.add(key)
                candidates.append(r)
        ab = acousticbrainz([r["recording_mbid"] for r in candidates])
        with_ab = [
            r
            for r in candidates
            if r["recording_mbid"] in ab
            and per_artist.get(r["artist_name"], 0) < PER_ARTIST
        ]
        for i in range(0, len(with_ab), 25):
            batch = with_ab[i : i + 25]
            meta = get(
                f"{LB}/metadata/recording/",
                recording_mbids=",".join(r["recording_mbid"] for r in batch),
                inc="artist",
            )
            for r in batch:
                mbid = r["recording_mbid"]
                recording = meta.get(mbid, {}).get("recording", {})
                artist = r["artist_name"]
                full = per_artist.get(artist, 0) >= PER_ARTIST
                if full or not recording.get("isrcs"):
                    continue
                per_artist[artist] = per_artist.get(artist, 0) + 1
                instruments = sorted(
                    {
                        rel["instrument"]
                        for rel in recording.get("rels", [])
                        if rel.get("type") == "instrument" and rel.get("instrument")
                    }
                )
                songs.append(
                    {
                        "id": mbid,
                        "title": r["track_name"],
                        "artist": artist,
                        "isrc": recording["isrcs"][0],
                        "listens": r["listen_count"],
                        "acousticbrainz": ab[mbid],
                        "instruments": instruments,
                    }
                )
        print(f"offset {offset}: {len(songs)} Songs so far", flush=True)
        if len(songs) >= TARGET:
            break
    OUT.write_text(json.dumps(songs[:TARGET], ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {min(len(songs), TARGET)} Songs to {OUT}")


if __name__ == "__main__":
    main()
