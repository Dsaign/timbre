# Spotify platform terms: what timbre may do

Researched 2026-10-28 from primary sources on developer.spotify.com only. This is a reading of the text, not legal advice.

## Summary verdict

1. **Search by title+artist / ISRC (Client Credentials, server-side): ALLOWED WITH CONDITIONS.** Search is still available in dev mode (max 10 results per call). You may store the Spotify track ID only "as strictly necessary", not indefinitely, and keep it up to date.
2. **ML/AI: COMPLIES if the separation is real.** Spotify data must never reach training or inference. A stored track ID is "Spotify Content", so keep it out of every model input and feature table. The ban on "analyze the Spotify Content ... for any purpose" is very broad.
3. **Previews: do not rely on `preview_url`** (marked Deprecated, "Can be null", cut for new apps since 2024-11-27). For a logged-out visitor, use the **Embed iframe** (a Widget, allowed for non-Premium users) or a **link-out**. The Web Playback SDK needs Premium and login.
4. **iFrame API events: they exist** (`ready`, `playback_started`, `playback_update`). Driving a background from play/pause is **UNCLEAR, leaning allowed**. The sync ban targets "visual media ... advertising, film, television program, slideshow, video". Do not sync to `position`, use artwork, or cover the embed.
5. **Dev mode: 5 users (not 25), owner needs Premium, quota counted per developer account.** The user cap is about authenticated users, so Client Credentials has none. Extended quota is organizations only with at least 250k MAU, so it is **NOT available** to timbre. A public portfolio site in dev mode is **UNCLEAR**: Spotify says dev mode is for "personal projects for non-commercial use by individual developers".

---

## Sources and dates

| Document | URL | Version / date shown |
|---|---|---|
| Developer Policy | https://developer.spotify.com/policy | "Effective as of 15 May, 2025" |
| Developer Terms | https://developer.spotify.com/terms | "Version 10, effective as of 15 May, 2025" |
| Widget Terms of Use (Embeds) | https://developer.spotify.com/documentation/embeds/terms | "Version 2.0. Effective as of 27 May 2014." |
| Design & Branding Guidelines | https://developer.spotify.com/documentation/design | no date shown |
| Compliance Tips | https://developer.spotify.com/compliance-tips | no date shown |
| Quota modes | https://developer.spotify.com/documentation/web-api/concepts/quota-modes | no date shown (reflects Feb–Jul 2026 changes) |
| Search reference | https://developer.spotify.com/documentation/web-api/reference/search | no date shown |
| Get Track reference | https://developer.spotify.com/documentation/web-api/reference/get-track | no date shown |
| iFrame API reference | https://developer.spotify.com/documentation/embeds/references/iframe-api | no date shown |
| Embeds troubleshooting | https://developer.spotify.com/documentation/embeds/tutorials/troubleshooting | no date shown |
| Blog: Changes to the Web API | https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api | 2024-11-27 |
| Blog: Extended access criteria | https://developer.spotify.com/blog/2025-04-15-updating-the-criteria-for-web-api-extended-access | 2025-04-15 |
| Blog: Developer access & security | https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security | 2026-02-06, update 2026-03-09 |
| Feb 2026 migration guide | https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide | Feb 2026 (info note added Jul 2026) |
| Changelogs Feb/Mar/May/Jul 2026 | https://developer.spotify.com/documentation/web-api/references/changes/february-2026 (and `march-2026`, `may-2026`, `july-2026`) | monthly |
| Blog: Web API quota updates | https://developer.spotify.com/blog/2026-07-23-web-api-quota-updates | 2026-07-23 |

The newest post on the developer blog listing is from 2026-08-13 (Spotify Soloist). It does not change any of the points below.

---

## 1. Search endpoint via Client Credentials to find a track

**Verdict: ALLOWED WITH CONDITIONS**

Client Credentials can call catalog endpoints:
> "this flow does not include authorization, only endpoints that do not access user information can be accessed."
> — https://developer.spotify.com/documentation/web-api/tutorials/client-credentials-flow

Search and Get Track are on the list of endpoints that dev-mode apps can still use after the February 2026 changes ("Search for Item (GET /search) – Searches across the Spotify catalog …"; "Get Track (GET /tracks/{id})"). Search has a new limit:
> "[CHANGED] Search for Item (GET /search) – The limit parameter maximum value has been reduced from 50 to 10, and the default value has been changed from 20 to 5."
> — https://developer.spotify.com/documentation/web-api/references/changes/february-2026

ISRC lookup is documented:
> "The available filters are album, artist, track, year, upc, tag:hipster, tag:new, isrc, and genre. … The isrc and track filters can be used while searching tracks."
> — https://developer.spotify.com/documentation/web-api/reference/search

`external_ids` (which carries the ISRC) was removed in February 2026 and then restored: "[REVERTED] external_ids — Known external IDs for the track. … will continue to be available." (https://developer.spotify.com/documentation/web-api/references/changes/march-2026). Track `popularity` and `available_markets` are gone for dev-mode apps.

**Conditions on storing and caching.** "Spotify Content" is defined broadly:
> "'Spotify Content' means any content, data, information or material made available through the Spotify Platform … This may include … metadata …"
> — https://developer.spotify.com/terms (Section II)

A Spotify track ID comes from the platform, so read it as Spotify Content.

> "Storing and displaying content. Except as otherwise set out in these Developer Terms, you may not store, aggregate or create compilations or databases of Spotify Content, other than as strictly necessary to operate your SDA. You must use reasonable efforts to ensure that any data you display to users is the most up to date data available through the Spotify Platform, and to delete older data. Do not store Spotify Content indefinitely."

> "Local caching. Do not locally cache any Spotify Content, except as strictly necessary to enhance the performance of your SDA and its functionality, and limited to the temporary caching of: metadata and cover art; …"

> "Improper use. Do not improperly access, alter or store the Spotify Service or Spotify Content, including using any robot, spider, site search/retrieval application, or other tool to retrieve, duplicate, or index any portion of the Spotify Service or Spotify Content … making excessive service calls that are not strictly required for the proper functioning of your SDA;"
> — https://developer.spotify.com/terms (Section IV)

**What this means for timbre:**
- Look tracks up on demand, server-side, when a user wants to play a result. Server-side calls are fine. The text restricts what you do with data, not where the call runs. Keep the client secret on the server.
- A short-lived cache of `musicbrainz_id -> spotify_track_id` (with a TTL and refresh) reads as "strictly necessary … to enhance the performance". Running Search over the whole MusicBrainz catalog in advance to build a permanent mapping table reads like "create compilations or databases of Spotify Content", "index", and "excessive service calls". Avoid that.
- Storing the ID next to the open-catalog record is not banned outright. It still falls under "not indefinitely" and "most up to date". Keep it in a separate cache table with a timestamp, not as a permanent column of the catalog.

## 2. Machine learning / AI and "analysis"

**Verdict: ALLOWED WITH CONDITIONS (the design complies as described)**

Developer Policy, Section III ("Some prohibited applications"):
> "13. Do not analyze the Spotify Content or the Spotify Service for any purpose, including without limitation, creating new or derived listenership metrics, benchmarking, functionality, usage statistics, user metrics, or building profiles of users, including for the purpose of targeting them with advertising or marketing."
> "14. Do not use the Spotify Platform or any Spotify Content to train a machine learning or AI model or otherwise ingest Spotify Content into a machine learning or AI model."
> — https://developer.spotify.com/policy

Developer Terms, Section IV.2 ("Misuse of the Spotify Platform"):
> "using the Spotify Platform or any Spotify Content to train a machine learning or AI model or otherwise ingesting Spotify Content into a machine learning or AI model;"
> — https://developer.spotify.com/terms

The 2026-02-06 blog gives the reason: "advances in automation and AI have fundamentally altered the usage patterns and risk profile of developer access".

**Does the design comply?** If the model only sees MusicBrainz or other open data and the user's text, and Spotify is only used to resolve a playback target after ranking, the text has nothing to object to. "Otherwise ingest … into a machine learning or AI model" covers inference as well as training. So the rule is: no Spotify field (ID, name, ISRC from Spotify, artwork, preview, availability) may ever be a model input, feature, filter, or embedding.

**Does storing the track ID next to the catalog record cause a problem?** Not under the ML clause by itself. Two places to be careful:
- Do not use "has a Spotify match" or "found on Spotify" as a ranking signal or filter fed back into the model or its evaluation. That is arguably ingesting or analyzing Spotify Content. Filtering results after ranking, only for display, is a grey area. It is safest to show all results and turn off the button when there is no match.
- Do not log or aggregate Spotify lookup outcomes (match rates, which tracks users played) for analysis. Item 13's "for any purpose" covers it.

Keeping the cache in a separate table, as in Q1, also makes this separation easy to show.

## 3. Previews and ways to hear a track without login

**`preview_url`: UNCLEAR at best. Assume it is null.**

> "Effective today, new Web API use cases will no longer be able to access or use the following endpoints and functionality … 30-second preview URLs, in multi-get responses (SimpleTrack object) … These changes will impact … New apps that are registered on or after today's date"
> — https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api

The current Search and Get Track references mark the field:
> "preview_url string Nullable Deprecated — A link to a 30 second preview (MP3 format) of the track. Can be null"
> — https://developer.spotify.com/documentation/web-api/reference/search , https://developer.spotify.com/documentation/web-api/reference/get-track

The blog names only "multi-get responses (SimpleTrack object)". The field is "Deprecated" everywhere, though, and new apps are affected. No primary source promises that a new app gets a non-null `preview_url`. Do not build on it. Any clip you do get falls under Policy V.2: "Audio Preview Clips must be accompanied by a link back to the applicable content … You must not offer Audio Preview Clips as a standalone service or product."

**Options for a visitor who is not logged in:**

| Option | Login / Premium needed? | How much audio (per docs) | Source |
|---|---|---|---|
| Spotify Embed (iframe) | No. Widgets "may be made available to Spotify users who do not subscribe to the Premium service" | Not stated exactly. The docs only say "In some situations the Embed will only stream a preview clip of less than 30 seconds", for example if `allow="encrypted-media"` is removed or the browser is unsupported. Full playback appears to depend on the visitor's own Spotify session. The docs do not spell out what a logged-out visitor hears. | https://developer.spotify.com/policy (IV.1), https://developer.spotify.com/documentation/embeds/tutorials/troubleshooting |
| iFrame API (same embed, scriptable) | Same as Embed | Same as Embed | https://developer.spotify.com/documentation/embeds/references/iframe-api |
| Link-out to open.spotify.com | No (Spotify handles it) | Whatever Spotify gives that user | Design guidelines, "Linking to Spotify" |
| Web Playback SDK | Yes: "requires a Spotify Premium subscription", plus user OAuth. Dev mode also caps users at 5. | Full track | https://developer.spotify.com/documentation/web-playback-sdk |

Policy IV.1: "Streaming of music sound recordings through the Spotify Platform shall only be made available to subscribers to the Premium Spotify Service. Please note that (i) Widgets and (ii) Audio Preview Clips may be made available to Spotify users who do not subscribe to the Premium service". The Web Playback SDK would make timbre a "Streaming SDA" (Compliance Tips lists "Apps using Web Playback SDK to play music").

**Practical answer:** Embed iframe, or a link-out, for each result. The Embed is a Widget, governed by the Widget Terms: "You shall display the Spotify Widgets in the form made available by Spotify, without alteration … You shall not obfuscate the Spotify Widgets in any way" (https://developer.spotify.com/documentation/embeds/terms). The Terms also note that "Widgets are not included in the definition of an SDA" (https://developer.spotify.com/terms, Section II).

## 4. iFrame API events and driving the WebGL background

**Events exposed: YES.**
> "ready — This event fires after an Embed has initialized and is ready to stream content"
> "playback_started — This event fires when a track or podcast episode starts playing. … receive an object with … playingURI (string)."
> "playback_update — This event fires after the state of playback changes. Playback state changes can occur by the user tapping on the playback controls in the Embed … playingURI (string), isPaused (bool), isBuffering (bool), duration (number) and position (number)."
> — https://developer.spotify.com/documentation/embeds/references/iframe-api

Controller methods include `loadUri`, `play`, `togglePlay`, `seek` (same page). The Embeds overview mentions podcast episodes for the iFrame API, but the event docs explicitly cover tracks.

**Using the events to animate the background: UNCLEAR, leaning ALLOWED WITH CONDITIONS.** The relevant clauses:

> "6. Do not synchronize any sound recordings with any visual media, including any advertising, film, television program, slideshow, video, or similar content."
> — https://developer.spotify.com/policy (III.6)

> "g. Synchronization. You may not synchronize any sound recordings accessed via the Spotify Platform with any visual media, including any advertising, film, television program, slideshow, video, or similar content."
> — https://developer.spotify.com/documentation/embeds/terms (Spotify Content Restrictions)

> "Synchronization: Syncing sound recordings accessed via the Spotify Platform with other recordings, lyrics, or video."
> — https://developer.spotify.com/compliance-tips

> "Artwork must be kept in its original form. Don't animate or distort it in any way. This includes applying overlays and blurring."
> — https://developer.spotify.com/documentation/design ("Using our content")

No primary source mentions "visualizer" for Web API or Embeds. (A 2026-08-13 blog post on Spotify Soloist, a separate local client, suggests "an LED matrix visualizer" for that product only. That is not permission for Embeds.)

How this reads: every example in the sync clause is authored visual media timed to the recording (ads, film, TV, slideshow, video). A generic background that changes state on a play/pause *user action* is not timed to the sound recording. That is a reasonable reading, but Spotify has not said so. Conditions that keep timbre on the safe side of the text:
- Use only binary state (`isPaused`, `isBuffering`, or your own button click). Do not map `position` or `duration` to visuals frame by frame. That moves toward "synchronize".
- Never use Spotify audio (the embed is cross-origin, so you cannot read it anyway), artwork colors, or metadata as visual input. This matches your design and also stays clear of Policy III.13 ("analyze").
- Do not render the WebGL layer over the embed, and do not lower its contrast or opacity. Widget Terms: "shall not obfuscate the Spotify Widgets in any way".
- The cleanest option is to drive the animation from timbre's own "preview" button click instead of from Spotify events. Then nothing Spotify-derived feeds the visuals.

## 5. Development mode vs extended quota mode (as of 2026-10-28)

**User cap: 5, not 25.**
> "Note: The app owner must have a Spotify Premium account for apps in development mode to function. Up to 5 authenticated Spotify users can use an app that is in development mode … Each Spotify user who installs your app will need to be added to your app's allowlist before they can use it."
> — https://developer.spotify.com/documentation/web-api/concepts/quota-modes

Timeline (https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security): from 2026-02-11 new dev-mode apps require Premium, "one Development Mode Client ID", "up to five authorized users", and "a smaller set of supported endpoints". Existing apps followed on 2026-03-09, except that endpoint restrictions for existing apps were postponed. July 2026 raised the Client ID limit to 25 and changed quota counting: "API quotas for development mode are now counted per developer account rather than per Client ID." (https://developer.spotify.com/documentation/web-api/references/changes/july-2026). Going over quota returns `429` with `"reason": "QUOTA_EXCEEDED"`. No numbers are published: "The specific groupings and limits are subject to change."

**Does the cap apply to Client Credentials?** The text ties the cap to "authenticated Spotify users" and the allowlist. A Client Credentials token has no user, so the user cap does not apply on its face. The per-developer-account **quota** does apply to every request. Spotify does not say this in so many words; it is a reading.

**Extended quota criteria (since 2025-05-15):**
> "as of May 15th 2025, Spotify only accepts applications from organizations (not individuals). … Implementation requirements: Established Business Entity (legally registered business or organisation); Operating an active, and Launched Service; Maintaining a minimum of active users (at least 250k MAUs); Being available in key Spotify markets; Commercial Viability; Adherence to Terms"
> — https://developer.spotify.com/documentation/web-api/concepts/quota-modes

timbre cannot qualify.

**Can a public portfolio site run in dev mode? UNCLEAR.**
> "Development Mode will be reduced in scope while continuing to support learning, experimentation, and personal projects for non-commercial use by individual developers. … It is intentionally limited and should not be relied on as a foundation for building or scaling a business on Spotify."
> — https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security

> "Spotify grants to you a … revocable right … [to] develop and distribute Streaming SDAs and Non-Streaming SDAs that comply with the Branding Guidelines: (i) for private personal use; …"
> — https://developer.spotify.com/terms (Section III.1)

A non-commercial portfolio by one developer fits "personal projects for non-commercial use by individual developers". No clause forbids public visitors who never log in. "Private personal use" in the license is ambiguous: it could mean the developer's own use, or the end users' personal (non-business) use. Section III.10 of the Policy uses the same idea for end users ("Spotify is for personal, non-commercial use which means it can't be broadcast or played publicly from a business"). The real practical limit is the unpublished quota: heavy public traffic could hit `429 QUOTA_EXCEEDED`.

## 6. Branding and attribution

**Verdict: ALLOWED WITH CONDITIONS**

> "Attribution. If you display any Spotify Content you must clearly attribute the content as being supplied and made available by Spotify, by using the Spotify Marks. … Metadata, cover art and Audio Preview Clips must be accompanied by a link back to the applicable album, content or playlist on the Spotify Service. You must not offer metadata, cover art, and/or Audio Preview Clips as a standalone service or product."
> — https://developer.spotify.com/policy (II.4)

From https://developer.spotify.com/documentation/design:
- "If you use any Spotify metadata (including artist, album and track names, album artwork, and audio playback) it must always be accompanied by the Spotify brand."
- "you must always attribute content from Spotify with the logo. In partner integrations, you should always use our full logo (icon + wordmark)." The icon alone is allowed "only if you do not have enough room for the full logo".
- Link text: "If the Spotify app is not installed then the link should say, GET SPOTIFY FREE. If the Spotify app is installed then use any of the following text strings: OPEN SPOTIFY, PLAY ON SPOTIFY or LISTEN ON SPOTIFY". A website cannot know whether the app is installed, so "PLAY ON SPOTIFY" / "LISTEN ON SPOTIFY" is the natural choice. The guideline does not list "Preview on Spotify", so use one of the listed strings.
- Logo: "The Spotify logo should never be smaller than 70px in digital … The Spotify icon should never be smaller than 21px in digital". "The Spotify green logo should only be used on a black or white background, for any other background you should use a monochrome logo." Keep the exclusion zone and do not place it "in a busy area, or in low-contrast areas". This matters over an animated WebGL background: put the logo on a solid panel.
- Artwork, if shown: original form, no crop, no overlay, "Don't animate or distort it in any way", rounded corners 4px (small/medium) / 8px (large).
- Metadata: "Track, artist, playlist, and album titles must always be presented with the metadata provided by Spotify." and "Don't manipulate any content or metadata."

Naming: "the name should not begin with 'Spot' or be confusing in sound or spelling to Spotify. Unless you have applicable permissions, don't imply any endorsement" (Policy VI). "timbre" is fine.

**Practical point:** show timbre's own MusicBrainz title and artist as the result, and the Spotify embed or "Listen on Spotify" button as a separate, clearly branded element. If you display Spotify's own title or artist strings, they must be unmodified and attributed. Do not mix them with MusicBrainz strings.

## 7. Combining with other services / discovery apps on non-Spotify data

**Verdict: UNCLEAR (no explicit ban on discovery apps; one broad clause is a risk)**

> "5. Do not create any product or service which is integrated with streams or content from another service."
> — https://developer.spotify.com/policy (III.5)

> "f. Integration with Third Party Services. You shall not create any product or service by integrating the Spotify Platform, Spotify Service or Spotify Content with (i) any non-interactive internet webcasting service or (ii) streams from another service."
> — https://developer.spotify.com/documentation/embeds/terms

> "Spotify content should never be seated next to content from similar services. … Platforms that aggregate content from multiple audio providers must give Spotify fair treatment - anything made available to all other partners must be available to Spotify."
> — https://developer.spotify.com/documentation/design ("Browsing Spotify content"). The section applies "If your app links to a user's Spotify account and there's a dedicated space to display Spotify content", which timbre does not do.

> "11. Do not build products or services that mimic, or replicate or attempt to replace a core user experience of Spotify … Your product or service must add independent value or functionality that improves users' interactions with Spotify."
> — https://developer.spotify.com/policy (III.11)

> "9. Do not build an SDA that enables the transfer of data to another service, except …"
> — https://developer.spotify.com/policy (III.9)

No clause bans a recommendation or discovery app that ranks with its own data and links to Spotify. Compliance Tips lists "Creating a playlist discovery website with pay-per-click advertising on it" as an *allowed* example (https://developer.spotify.com/compliance-tips). Spotify's own extended-access criteria mention promoting "artists and creator discovery" (2025-04-15 blog).

The risk is III.5's "content from another service". The Widget Terms version says "streams from another service", which suggests the target is mixing audio streams. MusicBrainz metadata is not a stream. Still, the Policy wording, "content", is wider. Lower the risk by:
- not offering playback from any other audio provider (YouTube, Apple, Deezer embeds) next to Spotify;
- not merging Spotify metadata into MusicBrainz records, or MusicBrainz data into what you show as Spotify content;
- not exporting Spotify IDs or data to other services (III.9).

---

## Open risks

1. **III.5 "content from another service"** is broad and not defined. A strict reader could say that showing MusicBrainz metadata next to a Spotify embed is "integrated with … content from another service". Nothing in the docs settles it.
2. **Synchronization (III.6 / Widget Terms g)** has no exception for ambient visuals. Event-driven state changes are a reasonable reading but not confirmed. Driving the animation from timbre's own click events is the most defensible choice.
3. **The "analyze … for any purpose" clause (III.13)** has no limit. Any logging, metrics or evaluation over Spotify lookups (match rates, play counts) could be caught by it. Do not collect them.
4. **Storing track IDs.** "Strictly necessary" and "not indefinitely" have no numbers. Pick and document a TTL. Avoid bulk pre-matching of the catalog.
5. **Dev-mode quota is unpublished and per developer account.** A public site could hit `429 QUOTA_EXCEEDED` with no way to raise it, since extended quota is closed to individuals. Plan to degrade to a plain link.
6. **License wording "for private personal use"** (Terms III.1) is ambiguous for a public website. Spotify's dev-mode statements ("personal projects for non-commercial use by individual developers") support a non-commercial portfolio, but nothing says so explicitly.
7. **How much a logged-out visitor hears in the Embed is not documented.** The docs only describe cases where it falls back to a "preview clip of less than 30 seconds".
8. **`preview_url` is Deprecated and may disappear entirely.** Do not depend on it.
9. **The Widget Terms are dated 2014** and the Design/Compliance pages carry no dates. Spotify can change all of these at any time ("the most current version will always be posted on our website"). Check again before launch.
10. **Lowest-risk fallback, not covered by the docs:** skip the Web API and link to an open.spotify.com search URL built from title+artist. No client ID, no stored Spotify data, no quota. No primary source documents or forbids that URL format, so it is outside the docs here.
