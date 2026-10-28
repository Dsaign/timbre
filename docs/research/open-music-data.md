# Open music data for timbre's text-to-song matching

Checked on 2026-10-28 against primary sources (project docs, licence pages, dump directory listings, live API calls). Anything not verified that day is marked *(unverified)*.

## Summary

- **The catalog comes from MusicBrainz. Its core data is CC0.** The core data has 40.7M recordings, and **6.37M unique ISRCs** are attached to recordings, which makes Spotify lookup exact. **Performer-instrument relationships** ("David Gilmour – electric guitar") are core data too, so they are also CC0.
- **MusicBrainz tags and genres are not CC0.** They are *supplementary data* under **CC BY-NC-SA 3.0**. A non-commercial portfolio may use them with credit to MusicBrainz, and data derived from them (for example tag-based vectors, if published) must carry the same licence. In practice the tags are mostly genre words. Mood words are rare.
- **Per-recording mood, instrumental and danceability come from AcousticBrainz.** It is **CC0**, keyed by MusicBrainz recording MBID, and has had no new data since 2022. The final dumps (2022-06-23, 29.46M submissions, about 7M distinct recordings) **can still be downloaded**, and the read API **still answered on 2026-10-28**. MetaBrainz itself says the classifier quality is limited, so treat these as weak signals.
- **ListenBrainz (CC0) answers "is this song well known?"** It gives listen counts per recording or artist and a metadata API that returns ISRCs, tags and instrument relationships in a single call.
- **Discogs dumps (CC0)** add release-level genres and styles. They are optional.
- **Not suitable as the main source:** MTG-Jamendo, FMA, Song Describer, MagnaTagATune and MusicCaps contain Creative Commons or indie music that is mostly not on Spotify, or YouTube clips with no title or artist. Several are also research-only or NC. The MSD Last.fm tags and the Last.fm API are non-commercial only, and Music4All is built on Spotify API features, which rules it out.

## Recommendation

**Smallest combination: MusicBrainz (core + derived dumps, or the API) + AcousticBrainz high-level dump + ListenBrainz popularity.**

1. **Pick the catalog.** Start from artists you care about, or from ListenBrainz popularity (`/1/popularity/top-recordings-for-artist/{artist_mbid}`, `POST /1/popularity/recording`). Map each recording to its canonical version using the MetaBrainz *canonical* dump (CC0).
2. **Keep only recordings that have** (a) at least one ISRC in MusicBrainz, (b) an AcousticBrainz high-level document for the same recording MBID (or a canonical sibling), and (c) a listen count above a threshold.
3. **Build one text document per song** and embed it with a multilingual text-embedding model, so Portuguese and English queries share one space. The document holds:
   - genre tags from the recording, release group and artist, weighted by vote count (BY-NC-SA)
   - performer-instrument relationships (CC0), plus instrument-like tags
   - AcousticBrainz high-level labels turned into words above a probability threshold, e.g. `mood_relaxed=relaxed (0.82)` → "relaxed, calm", `voice_instrumental=instrumental`, `danceability=danceable`, `timbre=dark`, `mood_aggressive`, `mood_acoustic`, `moods_mirex` cluster (CC0)
   - optional: AcousticBrainz BPM and key (CC0), and Discogs styles (CC0)
4. **Optionally keep a second vector** of the numeric AB probabilities (around 20 dimensions) for re-ranking. Turn the query into the same space by asking an LLM, or using keyword rules, to map "calm piano for studying" to `mood_relaxed↑, voice_instrumental↑, instrument:piano`.
5. **Spotify lookup** uses the ISRC search `isrc:XXXX`, with title plus artist as a fallback. MetaBrainz Labs also has `spotify-id-from-mbid` / `spotify-id-from-metadata` lookup endpoints.

**Starting size:** 5,000–20,000 recordings. About **10k** is a good first target. Example: the top ~10–20 recordings for each of ~600–1,000 well-known artists across genres, including Brazilian artists for the PT audience. This fits easily in pgvector (10k × 768 floats ≈ 30 MB). It can be built through the APIs at 1 req/s in a few hours, so you avoid loading the 7 GB MusicBrainz dump and the ~40 GB AcousticBrainz dump. If you scale past ~50k, switch to the dumps.

**Licence posture for timbre:**
- CC0 sources (MB core, AB, LB, Discogs, Wikidata) need no attribution, though credit is good practice.
- If you use MB tags/genres: attribute MusicBrainz, keep the project non-commercial, and put any redistributed tag-derived data under CC BY-NC-SA 3.0.
- A fully CC0 variant is possible: drop the MB tags and use the AB genre classifiers plus Discogs styles instead. It gives noticeably worse genre signal.

**Known gaps:**
- No open source has rich, reliable *mood* text for mainstream songs. AB classifiers are the only scaled option, and MetaBrainz calls their quality limited.
- Instrument relationships exist mainly for well-documented releases.
- Expect the matching to be "genre + coarse mood/instrumental" quality, not caption quality. The only free-form caption datasets (Song Describer, MusicCaps) are useful for **evaluating** the text encoder, not as a catalog.

## Comparison table

| Source | Sound/mood/instrument data per song | Coverage | Licence | Commercial / portfolio | Access | Maintained? |
|---|---|---|---|---|---|---|
| MusicBrainz core | Recordings, artists, ISRCs, performer-instrument relationships | 40.7M recordings; 6.37M unique ISRCs; 1,059 instruments | CC0 | Yes / yes | API 1 req/s per IP + User-Agent; dumps (`mbdump` 7 GB, JSON dumps) twice a week | Yes (stats and dump dated 2026-10-28) |
| MusicBrainz tags/genres | Folksonomy tags; 2,216 curated genres; vote counts | 246k distinct tags, 20.5M tag applications; sparse on obscure recordings | CC BY-NC-SA 3.0 (supplementary) | No / yes, with attribution + SA | `mbdump-derived` (502 MB) or API `inc=tags+genres` | Yes |
| AcousticBrainz | High-level: danceability, gender, genre ×4 models, mood_acoustic/aggressive/electronic/happy/party/relaxed/sad, moods_mirex, timbre, tonal_atonal, voice_instrumental, ismir04_rhythm; low-level: BPM, key, loudness | 29.46M submissions, about 7M distinct recording MBIDs | CC0 | Yes / yes | Final dumps: high-level JSON 30 × ~1–2 GB `.tar.zst`; CSV feature dumps; 100k sample; read API still live | Frozen since 2022 (no new data) |
| ListenBrainz | Popularity (listen and user counts); similar recordings/artists (labs); metadata API returns MB tags, ISRCs, instrument relationships | Hundreds of millions of listens | CC0 (dumps); tags via API are MB supplementary data | Yes / yes | API max 1 call/s; full dumps twice a month (listens 233 GB, stats 23 GB) | Yes (dump 2026-10-15) |
| Discogs | Genres and styles (release level) | Monthly XML; releases 10.5 GB gz | CC0 | Yes / yes | Monthly dumps (last 2026-10-01) | Yes |
| Wikidata | Genre (P136), instruments of performers; MB/ISRC cross-ids | Only ~29k items with MB recording ID, ~31k with ISRC, ~6.4k of those with genre | CC0 (structured data) | Yes / yes | SPARQL (60 s timeout), dumps | Yes |
| FMA | 161-genre taxonomy, user tags, librosa features (+ Echonest subset) | 106,574 CC-licensed indie tracks | Metadata CC BY 4.0; audio per artist | "Meant for research" | Zip downloads | Static (2017) |
| MTG-Jamendo | 87 genre, 40 instrument, 56 mood/theme tags | 55,525 tracks; 18,486 with mood; 25,135 with instrument | Metadata CC BY-NC-SA 4.0; "solely for non-commercial research and academic use" | No / borderline | GitHub + download script | Repo static |
| Song Describer | Free-text captions | 1,106 captions, 706 Jamendo tracks | CC BY-SA 4.0 (Zenodo) | Yes (SA) / yes | Zenodo | Static (2023) |
| MusicCaps | Aspect list + caption | 5,521 YouTube 10 s clips; no title/artist | CC BY-SA 4.0 | Yes (SA) / yes, but audio on YouTube | CSV of YouTube IDs | Static |
| MagnaTagATune | 188 crowd tags | ~25.8k clips, Magnatune label *(unverified)* | Not stated on host page | Unclear | City Univ. mirror | Static (2009) |
| MSD + Last.fm | Last.fm tags (incl. moods), similarity | 505,216 tracks with tags; 522k unique tags | "Research only, strictly non-commercial" | No / risky | Static download | Static (2011) |
| Last.fm API | Track/artist tags (rich moods) | Large | Last.fm API ToS: non-commercial only; must credit and link Last.fm; delete data on termination | No / yes (NC), with attribution | Live API, key required | Yes |
| Music4All | Spotify features, Last.fm tags, lyrics | 109,269 songs | On request, academic | No (built on Spotify data, which rules it out) | Email request | Static |

## MusicBrainz

- **Data:** the recording entity (title, artist credit, length, ISRCs, first release date) and relationships. Recording/release `instrument` and `vocal` performer relationships are core data and therefore CC0. Tags and genres are user-voted on recordings, release groups and artists, and the genres are a curated list of tags. Sample on 2026-10-28 for "Speak to Me / Breathe": 21 recording tags, 31 release-group tags and 16 artist tags, almost all genre words, plus instrument relationships (drums, Hammond organ, electric guitar) and 2 ISRCs.
- **Coverage (2026-10-28):** 40,733,533 recordings; 3,026,037 artists; ISRCs 6,550,218 (6,374,492 unique); 2,216 genres; 1,059 instruments; 246,222 aggregated tags.
- **Licence:** "The core data … is licensed under the CC0". "The remaining portions … Creative Commons Attribution-NonCommercial-ShareAlike 3.0". The supplementary portion includes "user submitted annotations, tags (including genre associations) and ratings". The Live Data Feed (replication) is also CC BY-NC-SA 3.0.
- **Access:** API limit is "on average 1 request per second" per source IP, and above that **all** requests get 503. A meaningful `User-Agent: App/version ( contact )` is required. Dumps are produced twice a week: `mbdump.tar.bz2` (7 GB, core), `mbdump-derived.tar.bz2` (502 MB, tags, ratings, annotations; "you will certainly need this if you want genre data"), and JSON dumps (`recording.tar.xz` 33 MB, `release.tar.xz` 22 GB, …).
- **Status:** actively maintained. Latest fullexport is `20261028-002228`.
- URLs: https://musicbrainz.org/doc/About/Data_License · https://musicbrainz.org/doc/MusicBrainz_Database · https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting · https://musicbrainz.org/doc/MusicBrainz_Database/Download · https://data.metabrainz.org/pub/musicbrainz/data/fullexport/ · https://data.metabrainz.org/pub/musicbrainz/data/json-dumps/ · https://musicbrainz.org/statistics · https://musicbrainz.org/doc/Genre

## AcousticBrainz

- **Status:** data collection stopped in 2022. The blog said "the data simply isn't of high enough quality to be useful for much at all": key detection was accurate only on some styles, BPM is often wrong, there are no confidence values, and the genre models "didn't work very well". The site says: "For now, the website and its API will continue to be available". A live call to `/api/v1/{mbid}/high-level` returned 200 with data on 2026-10-28.
- **Data:** the high-level classifiers listed in the table. Each gives a `value`, a `probability` and an `all` class-probability map (e.g. `voice_instrumental.all.instrumental`). Published accuracies include danceability 92.4% (306 tracks), voice/instrumental 93.8% (1,000 excerpts), timbre dark/bright 94.3%, tonal/atonal 97.7% and gender 87.2%. The training sets are small in-house MTG collections, which is why quality on a wide catalog is weaker. Low-level CSV feature dumps contain BPM, key/scale, danceability, loudness and dynamic complexity.
- **Coverage:** 29,460,584 submissions. Each recording MBID has one or more files (`mbid-n.json`, and `-0` always exists). Deduplicated, that is "approximately 7 million" recordings. The deduplicated dump was announced as "Pending" and never appeared in the directory.
- **Licence:** "All of the data contained in AcousticBrainz is licensed under the CC0 license".
- **Access:** `acousticbrainz-highlevel-json-20220623-{0..29}.tar.zst`, each 0.5–2 GB, about 40 GB in total *(sum estimated from listing)*. Also low-level JSON, low-level CSV features and a 100k sample. The files are keyed by MusicBrainz recording MBID, so the join with MB is direct. Some MBIDs have since been merged in MB, so resolve them through MB redirects or canonical mapping.
- URLs: https://acousticbrainz.org/ · https://acousticbrainz.org/download · https://acousticbrainz.org/data · https://acousticbrainz.org/datasets/accuracy · https://data.metabrainz.org/pub/musicbrainz/acousticbrainz/dumps/ · https://blog.metabrainz.org/2022/02/16/acousticbrainz-making-a-hard-decision-to-end-the-project/

## ListenBrainz

- **Data:** listen histories; popularity per recording, artist and release group (`total_listen_count`, `total_user_count`); top recordings per artist. `/1/metadata/recording` (GET/POST, `inc=artist tag release`) returns MB metadata including ISRCs, instrument relationships and tags with `genre_mbid`. MetaBrainz Labs hosts similar-recordings and similar-artists viewers, plus mapping lookups (`spotify-id-from-mbid`, `apple-music-id-from-mbid`, …).
- **Licence:** ListenBrainz PostgreSQL dumps are CC0, "Commercial use: Allowed, but financial support strongly urged". The MusicBrainz canonical dumps are also CC0. The MLHD+ derived dataset is "Non-commercial use only". Tags returned through LB are MB supplementary data, so the MB BY-NC-SA terms still apply.
- **Access:** the API asks clients to "never make more than ONE call per second", and `X-RateLimit-*` headers are returned. Full dumps come twice a month and incrementals daily. Latest full dump is 2026-10-15: listens 233 GB, spark 232 GB, statistics 23 GB.
- **Status:** actively maintained.
- URLs: https://listenbrainz.readthedocs.io/en/latest/users/api/index.html · https://listenbrainz.readthedocs.io/en/latest/users/api/popularity.html · https://listenbrainz.readthedocs.io/en/latest/users/api/metadata.html · https://listenbrainz.readthedocs.io/en/latest/users/listenbrainz-dumps.html · https://metabrainz.org/datasets/postgres-dumps · https://metabrainz.org/datasets/derived-dumps · https://labs.api.listenbrainz.org/ · https://data.metabrainz.org/pub/musicbrainz/listenbrainz/

## Discogs

- **Data:** release- and master-level `genres` (broad) and `styles` (fine, e.g. "Bossa Nova", "Stoner Rock"). There is no recording-level mood or instrument data. Credits sometimes name instruments *(unverified as structured)*.
- **Licence:** "made available under the CC0 No Rights Reserved license".
- **Access:** monthly XML dumps. 2026-10-01: releases 10.5 GB gz, masters 600 MB, artists 476 MB, labels 87 MB. MB holds Discogs URLs as relationships, which can be used to join the two.
- **Status:** maintained (monthly).
- URL: https://data.discogs.com/

## Wikidata

- **Data:** genre (P136) on songs, albums and artists; instrument (P1303) on performers; cross-identifiers: MusicBrainz recording ID (P4404), ISRC (P1243).
- **Coverage (SPARQL, 2026-10-28):** 29,255 items with an MB recording ID, 30,804 with an ISRC, 6,419 items with both an MB recording ID and a genre. That is too thin at song level, though more useful at artist level.
- **Licence:** structured data is CC0 ("Wikidata requires a CC0 license"). The text of project pages is CC BY-SA.
- **Access:** SPARQL endpoint (timeouts apply) and full dumps at https://dumps.wikimedia.org.
- URLs: https://www.wikidata.org/wiki/Wikidata:Licensing · https://www.wikidata.org/wiki/Wikidata:Data_access

## Free Music Archive (FMA)

- 106,574 tracks, 16,341 artists, 161-genre hierarchy, user tags, librosa features. Echonest/Spotify features exist for 13,129 tracks. Do not use those, given timbre's no-Spotify-data policy.
- Licence: metadata CC BY 4.0, code MIT, audio under each artist's licence. "The dataset is meant for research purposes."
- Not useful as timbre's catalog: these are indie CC tracks, rarely on Spotify.
- URL: https://github.com/mdeff/fma

## MTG-Jamendo

- 55,525 tracks: 87 genre, 40 instrument and 56 mood/theme tags. 18,486 tracks have mood/theme tags and 25,135 have instrument tags. It is the best open *mood + instrument* tag vocabulary.
- Licence: metadata **CC BY-NC-SA 4.0**. "Made available solely for non-commercial research and academic use. Any other use … requires prior written authorization from Jamendo".
- Not a catalog for timbre (Jamendo music). Its tag vocabulary is useful as a reference for which mood/instrument words to map queries onto, and for training or evaluating a classifier.
- URL: https://github.com/MTG/mtg-jamendo-dataset

## Song Describer Dataset

- 1,106 free-text captions for 706 Jamendo tracks (e.g. "Calm sitar and Indian tabla with dramatic synthetic strings background"). Zenodo record licence **CC BY-SA 4.0** (2023-11-16). Code MIT.
- Use it as an **evaluation set** for the text side: check that PT/EN queries embed near the captions. It is not a catalog.
- URLs: https://github.com/mulab-mir/song-describer-dataset · https://doi.org/10.5281/zenodo.10072001

## MusicCaps

- 5,521 ten-second clips, each with an aspect list and a free-text caption written by musicians. Licence **CC BY-SA 4.0**. Only YouTube IDs and timestamps are given, with no title or artist, so it cannot map to Spotify songs. Use it only for text-side evaluation.
- URLs: https://www.kaggle.com/datasets/googleai/musiccaps · https://huggingface.co/datasets/google/MusicCaps

## MagnaTagATune

- Crowd tags from the TagATune game on Magnatune-label clips, plus Echonest features and similarity data. The host page states no licence. Magnatune is not mainstream music. Skip it.
- URL: https://mirg.city.ac.uk/codeapps/the-magnatagatune-dataset

## Million Song Dataset + Last.fm tags

- 943,347 matched tracks; 505,216 with at least one tag; 522,366 unique tags; 8.6M track–tag pairs; 56.5M similarity pairs. These are real, well-known songs, and the tags include moods.
- Licence: **"Research only, strictly non-commercial … Last.fm has the right to advertise and refer to any work derived from the dataset."** The data is from 2011 and is keyed by MSD/Echonest IDs, not ISRC or MBID. A public portfolio site is a grey area, so avoid it unless you confirm with Last.fm.
- URL: http://millionsongdataset.com/lastfm/

## Last.fm API

- The richest mood and descriptor tags for mainstream tracks.
- ToS: §3.1 "solely for non-commercial purposes". §2.3 allows storing the data, subject to local law. You "must credit Last.fm and include links to the Last.fm site" and use "powered by AudioScrobbler" branding. All rights stay with Last.fm (§4.5), and on termination you must delete all Last.fm data (§9.3). Commercial or research use: they ask you to email partners@last.fm before use.
- Possible as an *optional* enrichment for a non-commercial portfolio. It is not in the minimal set because of the attribution, deletion and research-use conditions.
- URL: https://www.last.fm/api/tos

## Music4All

- 109,269 songs with lyrics, clips, Last.fm tags and genres. Its audio features (danceability, energy, valence, …) and popularity "provided by the Spotify API", which conflicts with timbre's policy. Available by email request only.
- URL: https://sites.google.com/view/contact4music4all
