"""MetaBrainz API calls and parsers shared by catalog_import.py and fetch_seed.py."""

import asyncio
import logging
import os
from collections.abc import Mapping
from typing import Any, NotRequired, TypedDict

import httpx

from timbre_back.jobs import JobDeferred

log = logging.getLogger("timbre.metabrainz")
LISTENBRAINZ_API = "https://api.listenbrainz.org/1"
ACOUSTICBRAINZ_API = "https://acousticbrainz.org/api/v1"
ACOUSTICBRAINZ_BATCH = 25  # AcousticBrainz takes at most 25 recordings per call
METADATA_BATCH = 50  # recordings per ListenBrainz metadata call
TAGS_PER_SONG = 5
PAUSE = 1.1  # seconds before each call: MetaBrainz allows no more than 1 call/s
ATTEMPTS = 4
STATS_PAGE = 1000  # the most a ListenBrainz sitewide stats call returns


class Song(TypedDict):
    id: str  # MusicBrainz recording ID
    title: str
    artist: str
    isrc: str
    listens: int
    acousticbrainz: dict[str, dict[str, float]]
    instruments: list[str]
    tags: NotRequired[list[str]]  # missing in the seed (CC0 only)


class ApiUnavailable(JobDeferred):
    """A MetaBrainz API kept answering 429/5xx or could not be reached."""


def client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    # MetaBrainz asks for a contact (email or URL) in the User-Agent.
    contact = os.environ.get("METABRAINZ_CONTACT")
    if not contact:
        raise RuntimeError("set METABRAINZ_CONTACT (email or URL) in back/.env")
    return httpx.AsyncClient(
        headers={"User-Agent": f"timbre/0.1 ( {contact} )"},
        timeout=60,
        transport=transport,
    )


async def fetch_json(http: httpx.AsyncClient, url: str, **kwargs: Any) -> Any:
    """GET one call at a time, PAUSE apart; 429, 5xx and network errors back off."""
    for attempt in range(1, ATTEMPTS + 1):
        await asyncio.sleep(PAUSE * attempt**2)
        try:
            response = await http.get(url, **kwargs)
        except httpx.TransportError as e:
            if attempt == ATTEMPTS:
                raise ApiUnavailable(f"{url}: {e!r}") from e
            continue
        if response.status_code != 429 and response.status_code < 500:
            response.raise_for_status()
            return response.json()
        if attempt == ATTEMPTS:
            raise ApiUnavailable(f"{url} answered {response.status_code}")
        log.warning("%s answered %d, retrying", url, response.status_code)
    raise AssertionError("unreachable")


def high_level(docs: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    """AcousticBrainz high-level class probabilities, {classifier: {class: p}}."""
    return {
        name: {label: round(p, 3) for label, p in c["all"].items()}
        for name, c in docs["0"]["highlevel"].items()
    }


async def fetch_high_level(
    http: httpx.AsyncClient, recording_mbids: list[str]
) -> dict[str, dict[str, dict[str, float]]]:
    """High-level data of the recordings AcousticBrainz has analysed."""
    found: dict[str, dict[str, dict[str, float]]] = {}
    for i in range(0, len(recording_mbids), ACOUSTICBRAINZ_BATCH):
        batch = recording_mbids[i : i + ACOUSTICBRAINZ_BATCH]
        docs = await fetch_json(
            http,
            f"{ACOUSTICBRAINZ_API}/high-level",
            params={"recording_ids": ";".join(batch)},
        )
        found |= {mbid: high_level(docs[mbid]) for mbid in batch if mbid in docs}
    return found


async def recordings_metadata(
    http: httpx.AsyncClient, recording_mbids: list[str]
) -> dict[str, dict[str, Any]]:
    """ListenBrainz metadata (ISRCs, instrument credits, tags) per recording."""
    metadata: dict[str, dict[str, Any]] = await fetch_json(
        http,
        f"{LISTENBRAINZ_API}/metadata/recording/",
        params={"recording_mbids": ",".join(recording_mbids), "inc": "artist tag"},
    )
    return metadata


def to_song(
    recording_mbid: str,
    title: str,
    artist: str,
    listens: int,
    acousticbrainz: dict[str, dict[str, float]],
    recording: Mapping[str, Any],
) -> Song:
    """A Song from ListenBrainz's candidate fields, its high-level data and metadata."""
    return {
        "id": recording_mbid,
        "title": title,
        "artist": artist,
        "isrc": recording["isrcs"][0],
        "listens": listens,
        "acousticbrainz": acousticbrainz,
        "instruments": instruments(recording),
    }


def instruments(recording: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            rel["instrument"]
            for rel in recording.get("rels", [])
            if rel.get("type") == "instrument" and rel.get("instrument")
        }
    )


def top_tags(tags_by_level: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    """The most-voted tags of the most specific level that has any."""
    for level in ("recording", "release_group", "artist"):
        if tags_by_level.get(level):
            ranked = sorted(tags_by_level[level], key=lambda tag: -tag["count"])
            return [tag["tag"] for tag in ranked[:TAGS_PER_SONG]]
    return []
