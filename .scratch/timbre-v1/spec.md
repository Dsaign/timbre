Status: ready-for-agent

# timbre v1: describe music, get Matches

## Problem Statement

People often know the *feel* of the music they want ("violão calmo para estudar", "guitarra suja e voz rouca, clima de estrada à noite", "something dark and electronic to focus") but not the names of songs that have it. Music apps search by title, artist or genre, which is no help when all you have is a mood, an instrument or a texture. A visitor should be able to describe the music in their own words, in Portuguese or English, and get real songs they can listen to right away.

The project owner also has a second goal: to learn full-stack development and an AI-assisted workflow on a real, portfolio-quality system. That system has a Next.js front end, a Python ML back end, a vector database, background jobs, its own trained model measured against a baseline, and production-grade security. All of it must stay within the Spotify Developer Policy and the licences of open music data.

## Solution

timbre is a single page. It shows a frosted-glass search panel over a subtle animated waveform made of particles. Before any search, it offers clickable sample Descriptions that show what it can do. The visitor types a Description and submits it. timbre shows how many Matches it found and a grid of Songs, sized to fill the visitor's screen, with "carregar mais" for the next page. Each card shows the title and artist, plus 👍/👎 Feedback. Songs that are available on Spotify also get a Preview button and a "LISTEN ON SPOTIFY" link. Preview plays in a single Spotify player docked at the bottom. The background responds to the visitor's own actions: typing, submitting, and starting or stopping a Preview. Light and Dark themes are available.

Behind the page, a Catalog of about 10k well-known Songs is built only from open data (MusicBrainz, AcousticBrainz, ListenBrainz). A pretrained multilingual text model gives the baseline Fit. The project's own model, a small layer trained on top of it, improves Fit using visitor Feedback. A new model goes live only if it does no worse on a fixed Benchmark of 100 Descriptions. Spotify is used for Preview only and never reaches any model (ADR 0001).

## User Stories

### Searching

1. As a visitor, I want to type a Description of the music I want in my own words, so that I can find songs without knowing their names.
2. As a visitor, I want to describe a mood ("melancólico", "energético"), so that I get Songs with that feeling.
3. As a visitor, I want to describe an instrument ("piano", "violão", "sintetizador"), so that I get Songs featuring it.
4. As a visitor, I want to describe a preference such as a genre or era ("rock alternativo dos anos 90"), so that I get Songs in that style.
5. As a visitor, I want to mix mood, instrument and preference in one Description, so that I can be as specific as I like.
6. As a visitor, I want to write my Description in Portuguese or English, so that I can use whichever language comes naturally.
7. As a visitor, I want the search to accept up to 300 characters, so that I have room to describe what I want without writing an essay.
8. As a visitor, I want to submit by pressing Enter or clicking "Pesquisar", so that searching works the way I expect.
9. As a visitor, I want an empty Description to be blocked before it is sent, so that I don't get a meaningless search.
10. As a visitor, I want the page URL to contain my search, so that I can share it or come back to it.
11. As a visitor, I want to see clickable sample Descriptions on the home page before I search, so that I understand what kind of Descriptions timbre understands.
12. As a visitor, I want clicking a sample Description to fill the search box and run the search in one click, so that I can try timbre instantly.

### Matches

13. As a visitor, I want to see how many Matches my Description found, so that I know how broad or narrow it was.
14. As a visitor, I want the Matches shown in a grid that fills my screen, so that I see as many as fit without scrolling first.
15. As a visitor on a phone, I want the grid to adapt to my screen width with no horizontal scrolling, so that the page is comfortable on mobile.
16. As a visitor, I want resizing or rotating my screen to only re-arrange the grid (not reload it), so that I don't lose what I'm looking at.
17. As a visitor, I want a "carregar mais" button, so that I can see the next set of Matches.
18. As a visitor, I want each Match card to show the Song's title and artist, so that I know what it is.
19. As a visitor, I want the best-fitting Matches first, with well-known Songs slightly favoured, so that the top of the grid is the most useful.
20. As a visitor, I want the grid to appear immediately even while Spotify availability is still being checked, so that the page feels fast.
21. As a visitor, I want a skeleton grid while my search runs, so that I know something is happening.
22. As a visitor whose Description finds no Matches (for example random letters), I want a clear "Nenhuma música encontrada" message with sample Descriptions to click, so that I know what to try instead.
23. As a visitor, I want a friendly message when I search too often ("muitas buscas, tente em instantes"), so that I understand why nothing happened.
24. As a visitor, I want a friendly message if the service is unavailable, so that I am not left with a broken page.

### Preview

25. As a visitor, I want a Preview button on a card only when that Song is available on Spotify, so that I'm never offered something that doesn't work.
26. As a visitor, I want clicking Preview to play the Song in a single player docked at the bottom of the page, so that I can keep browsing while listening.
27. As a visitor, I want starting a Preview on another card to switch the docked player to that Song, so that only one Song plays at a time.
28. As a visitor, I want a "LISTEN ON SPOTIFY" link on cards whose Song is on Spotify, so that I can open the full track in Spotify.
29. As a visitor, I want cards whose Song is not on Spotify to show neither Preview nor the Spotify link, so that the card stays honest.
30. As a visitor, I want a temporary Spotify problem to simply hide the Preview button (and work again on a later search), so that one failure doesn't break the page.

### Feedback

31. As a visitor, I want to vote 👍 or 👎 on each Match, so that I can tell timbre whether that Song fits my Description.
32. As a visitor, I want my chosen thumb to stay highlighted, so that I can see what I voted.
33. As a visitor, I want to switch my vote from 👍 to 👎 (or back), so that I can fix a misclick.
34. As a visitor, I want to press the same thumb again to withdraw my vote, so that I can undo it entirely.
35. As a visitor, I want a short notice under the search box saying that Descriptions and votes are stored to improve the model, so that I know what happens with my input.
36. As the project owner, I want each visitor limited to one vote per Description and Song, so that one person cannot flood the Feedback.
37. As the project owner, I want Feedback stored without any information that identifies a person, so that timbre respects privacy law (LGPD).

### Background and look

38. As a visitor, I want a subtle animated waveform made of particles behind the page, so that the page feels musical and alive without distracting me.
39. As a visitor, I want the waveform to ripple softly while I type, so that the page responds to me.
40. As a visitor, I want the waveform to tighten and line up when I submit, and relax when the Matches appear, so that searching feels like the page is listening.
41. As a visitor, I want the waveform to grow warmer and livelier while a Preview plays, and calm down over about two seconds when it stops, so that the page reflects what I'm doing.
42. As a visitor who prefers reduced motion, I want the waveform to stay still (changing only colour between states), so that the page doesn't make me uncomfortable.
43. As a visitor, I want the animation to pause when the tab is hidden, so that it doesn't waste my battery.
44. As a visitor, I want frosted-glass panels that stay readable over the background, so that the interface is beautiful and legible.
45. As a visitor who prefers reduced transparency, I want solid panels instead of frosted glass, so that text is easy to read.
46. As a visitor, I want Light and Dark themes that follow my system setting by default, so that the page matches my device.
47. As a visitor, I want a toggle to switch theme, remembered on my next visit, so that I can choose what I like.
48. As a visitor, I want the background colours to change with the theme, so that the whole page feels consistent.
49. As a visitor, I want the page never to flash the wrong theme while loading, so that it feels polished.
50. As a keyboard or screen-reader user, I want the search box, buttons and votes to be labelled and reachable by keyboard, so that I can use timbre fully.

### Footer and credits

51. As a visitor, I want a footer crediting MusicBrainz, AcousticBrainz, ListenBrainz and Spotify, so that the data sources get the credit they require.
52. As a visitor, I want a GitHub mark in the footer that links to the public repository, so that I can see how timbre is built.

### Catalog and model (project owner)

53. As the project owner, I want to build a Catalog of about 10k well-known Songs from open data through the public APIs, so that timbre never depends on Spotify data for matching.
54. As the project owner, I want the import to respect each API's rate limit and to resume where it stopped, so that a long import survives interruptions.
55. As the project owner, I want only Songs with an ISRC and AcousticBrainz data in the Catalog, so that every Song can be described and found on Spotify reliably.
56. As the project owner, I want each Song's profile to combine its genres and tags, AcousticBrainz labels expressed as words, and instrument credits, so that Descriptions about mood, instrument and style can all find it.
57. As the project owner, I want a pretrained multilingual baseline model, so that timbre works from day one.
58. As the project owner, I want my own trained model on top of the baseline, so that I can study and show measurable ML improvement.
59. As the project owner, I want initial training pairs drafted from Catalog Songs (kept apart from the Benchmark), so that my model can be trained before any Feedback exists.
60. As the project owner, I want retraining to run as a background job that uses accumulated Feedback, so that the model improves as people use timbre.
61. As the project owner, I want a newly trained model to go live only if it scores no worse than the current one on the Benchmark, so that a bad training run never reaches visitors.
62. As the project owner, I want every model version recorded with its Benchmark score, so that I can show the model's progress over time.
63. As the project owner, I want a Benchmark of 100 Descriptions (about 40 hand-written, 60 drafted and reviewed), each with the Songs that should be Matches, so that "better" is a number.
64. As the project owner, I want the cutoff that decides what counts as a Match tuned on the Benchmark, so that the Match count means something.
65. As the project owner, I want the Popularity weight in the ordering tuned on the Benchmark, so that favouring well-known Songs never overrides Fit.

### Operations and security (project owner)

66. As the project owner, I want the Spotify lookup cache kept in a separate place that no ML code can read, enforced by the database itself, so that the Spotify Developer Policy is respected by construction.
67. As the project owner, I want expired Spotify cache entries deleted daily, so that Spotify data is never stored indefinitely.
68. As the project owner, I want Spotify lookups limited in parallel and retried with backoff on rate limits, so that timbre stays within its development-mode quota.
69. As the project owner, I want the API to accept requests only from the front end, so that nobody can use up my quota by calling it directly.
70. As the project owner, I want rate limits on searching and voting, so that scripts can't abuse timbre.
71. As the project owner, I want every input validated on both the front end and the API, so that malformed or malicious input is rejected early.
72. As the project owner, I want row level security and minimal grants on every table, so that a mistake in one place doesn't expose data.
73. As the project owner, I want all secrets kept out of git and checked automatically, so that keys never leak.
74. As the project owner, I want HTTPS everywhere and strict security headers, so that visitors are protected in transit.
75. As the project owner, I want an OpenAPI contract and a generated typed client, so that front end and back end can't drift apart silently.
76. As the project owner, I want CI to run lint, type checks, tests, the contract check, secret scanning and dependency and image scans, so that problems are caught before deploy.
77. As the project owner, I want the whole back end to run with one Docker Compose file, both locally and on the server, so that development and production match.
78. As the project owner, I want automatic server snapshots, so that Feedback, the one piece of data that can't be rebuilt, survives a disaster.

## Implementation Decisions

### Shape of the system

- The repository has two top-level parts: **front** (the Next.js app, deployed to Vercel) and **back** (a FastAPI service, a background worker, the Catalog import, and SQL migrations, deployed with Docker Compose on one VPS behind Caddy).
- The existing Next.js app moves into the front part in the first slice. In the same slice, its Base UI components and Phosphor icon set are replaced by Radix-based shadcn components and Lucide icons (ADR 0003). Brand marks use official SVGs.
- Visitors never call back directly. Searches, Preview lookups and Feedback go through front's server code, which calls back over HTTPS with a shared secret token and forwards the visitor's IP address. Back trusts the forwarded IP only when the token is valid. CORS is disabled on back.
- back is fully async (async database driver, async HTTP client for Spotify and the open-data APIs).

### API contract

- back publishes an OpenAPI 3.1 spec generated from its request and response models. The spec is committed to the repository, and front uses a typed client generated from it. CI fails if the committed spec and the code disagree. Interactive API docs are enabled in development only.
- Endpoints (described by behaviour, not exact paths):
  - **Search:** takes a Description (1–300 characters after trimming), a page size N (1–60, defaulting to 24) and an offset. Returns the total Match count and one page of Matches (Song ID, title, artist), ordered.
  - **Preview lookup:** takes a list of Song IDs (at most 60). Returns, for each one, either a Spotify track reference or "not available". Failures are reported as "not available" for that Song.
  - **Feedback:** takes a Description, a Song ID and a vote (up, down, or none to withdraw). Each (visitor, Description, Song) has at most one vote, and the latest wins.
  - **Sample Descriptions:** returns the short list shown on the home page and in the no-Matches state. It may be a static list served by front.
- Responses contain only the fields the UI needs. Errors never include stack traces or SQL. A rate-limited request returns HTTP 429.
- Request bodies are capped at about 16 KB. There are no uploads.

### Matching and ordering

- **Baseline Fit:** the Description and each Song's profile text are embedded with `intfloat/multilingual-e5-small` (384 dimensions, with "query:" and "passage:" prefixes). Fit is cosine similarity, computed with pgvector over Song vectors that are calculated ahead of time.
- **Song profile text:** MusicBrainz genres and tags, AcousticBrainz high-level labels above a probability threshold, written as words (for example relaxed, instrumental, dark, danceable), and instrument credits.
- **Own model (first version):** the e5 model stays frozen. A small trained layer works on top: a learned projection of the Description vector, plus a head that predicts AcousticBrainz label probabilities from the Description and compares them with the Song's real values. Fit combines the two. It trains on CPU. Fine-tuning e5 itself is out of scope.
- **Training data:** pairs drafted by an LLM from Catalog Songs, then 👍 Feedback (positives) and 👎 Feedback (hard negatives). Benchmark Descriptions and Songs paired with them in the Benchmark are never used for training. Anything too close to a Benchmark Description is excluded too.
- A Song is a **Match** when its Fit is above the cutoff. The count is the number of Matches. The cutoff is tuned on the Benchmark, stored with the model version, and re-tuned whenever a model is promoted.
- **Order of Matches:** Fit plus a small Popularity weight (from ListenBrainz listen counts), with the weight tuned on the Benchmark. Popularity never turns a non-Match into a Match. Audio signals affect only Fit, so fixed global weights for audio features are not used.
- Spotify Audio Features are not used: new apps can no longer access them, and the Developer Policy forbids it (ADR 0001).

### Data model (Postgres with pgvector, one database, separate schemas and roles)

- **catalog:** Songs (MusicBrainz recording ID, title, artist, ISRC, Popularity), Song profile text, AcousticBrainz label probabilities, Song vectors, model versions (artifact location, Benchmark score, cutoff, Popularity weight, promoted flag), Benchmark Descriptions with their expected Songs, and drafted training pairs.
- **feedback:** votes (Description, Song ID, vote, timestamps, salted visitor hash). Visitor hashes expire after a few days. The salt is a secret.
- **preview:** the Spotify cache (Song ID as a plain value with no foreign key, Spotify track reference or "not found", fetched at, expires at). Found and not-found entries are kept 24 hours. Errors are never cached.
- **jobs:** the background job queue, Postgres-backed.
- **Rate-limit counters** also live in Postgres. There is no Redis.
- **Roles:**
  - `ml_worker`: read and write catalog, read feedback, no preview access.
  - `api_search`: read catalog, insert, update and delete own votes in feedback, no preview access.
  - `api_preview`: preview only.
  - The API process uses separate connection pools for search/Feedback and for Preview.
- Row level security is enabled and forced on every table, with deny-by-default policies that allow each role only its own operations.
- **Migrations:** plain, numbered, descriptive SQL files applied in order (dbmate or a tiny runner). There is no ORM.
- Every query uses bound parameters. Building SQL from strings is blocked by a lint rule.

### Background jobs (worker)

- **Catalog import:** MusicBrainz, AcousticBrainz and ListenBrainz through their APIs (1 request per second, proper User-Agent), resumable, about 10k Songs selected by Popularity, keeping only Songs with an ISRC and AcousticBrainz data. Full data dumps are used only when the project owner asks (ADR 0002). Imported data is never committed to git.
- **Build vectors:** creates the profile text and embeddings for new or changed Songs.
- **Train → evaluate → promote:** trains the own model, scores it on the Benchmark, records the version, and promotes it only if its score is not worse than the current promoted version. The API switches to a newly promoted model without downtime.
- **Spotify cache cleanup:** runs daily and deletes expired entries.
- Model files live on a Docker volume and are registered in the model versions table.

### Spotify integration (ADR 0001)

- Lookups happen for the Matches shown on each page of the grid: by ISRC first, then title plus artist, using the Client Credentials flow (no user login).
- At most 4 lookups run at a time. On HTTP 429, honor `Retry-After` when present, otherwise exponential backoff with jitter (about 0.5 s, 1 s, 2 s), with at most 3 retries. After that the Song is "not available" for this request and is not cached.
- Preview uses the Spotify Embed through the iFrame API, as one shared player docked at the bottom. The page listens only for its play and pause events. Playback position, duration, artwork and audio are never used to drive visuals.
- The Spotify app stays in development mode. Branding follows Spotify's guidelines: the full logo at a minimum of 70 px, the wording "LISTEN ON SPOTIFY", and metadata shown unchanged.

### Front end

- The search form submits with GET to the home page. Before submitting, client code measures how many cards fit (columns × visible rows) and adds N to the URL. Without JavaScript, N is 24. Resizing never refetches: the layout only reflows.
- **Rendering:** a route-level loading state (skeleton grid), a Suspense boundary around the grid, and a separate Suspense boundary for each card's Preview controls, so the grid streams in before Spotify lookups finish.
- **Before any search:** the search panel and clickable sample Descriptions. A no-Matches result shows the message and the same sample Descriptions. Clicking a sample fills the input and searches in one action.
- **Feedback controls:** 👍/👎 per card, with the current vote highlighted. Pressing the other thumb switches the vote. Pressing the same thumb again withdraws it. Updates are optimistic and reverted on error.
- **Frosted glass:** real backdrop blur only on the search panel, the docked player, and one shared panel behind the grid. Cards use a more opaque tint with little or no blur. `prefers-reduced-transparency` switches to solid surfaces. Text meets WCAG AA contrast in both themes.
- **Themes:** Light and Dark, following the system by default, with a toggle remembered in local storage (next-themes; no cookie, no flash of the wrong theme).
- Server actions validate every input with the same rules as the API before calling back.
- **Footer:** credits MusicBrainz, AcousticBrainz, ListenBrainz and Spotify, plus the GitHub mark linking to the public repository.
- The UI language is pt-BR.

### Background waveform

- Raw WebGL2, with no 3D library. A ribbon of roughly 20–40k points is shaped by waves in a vertex shader. Depth of field is faked with point size and transparency by depth, plus a few drifting bokeh sprites. The look follows the reference image the project owner shared: a particle ribbon in deep navy and teal with a warm edge, kept low in contrast so it never pulls attention from the UI.
- **States and reactions:**
  - **idle:** slow drift, cool colours, low amplitude.
  - **typing:** each keystroke sends a soft brightness ripple along the ribbon, driven by one timestamp per keystroke.
  - **submitting:** the ribbon tightens and lines up horizontally.
  - **results shown:** the ribbon relaxes.
  - **Preview playing:** warmer colours and higher amplitude.
  - **Preview stopped:** eases back to idle over about 2 s.
  - All changes are smooth blends.
- A pure function maps (state, theme, reduced-motion) to target shader parameters. With reduced motion, the ribbon is static and only colours change.
- All colours live in one palette configuration per theme and state, so the look is easy to change.
- The animation pauses when the tab is hidden.

### Security

- **Secrets:** stored only in environment variables (Vercel for front, a permission-restricted env file on the VPS for back), with a names-only example file per service. Secrets: Spotify client ID and secret, the front-to-back token, one database password per role, and the IP-hash salt. gitleaks runs in a pre-commit hook and in CI. The git history was scanned and is clean.
- **Rate limits** per visitor hash:
  - Search: 30 per minute.
  - Feedback: 60 per hour.
  - When exceeded, back returns 429 and front shows a friendly message.
- **Privacy:** only Descriptions, votes and salted, expiring visitor hashes are stored. No raw IP addresses and no cookies.
- **HTTPS and headers:**
  - Vercel serves front over HTTPS. Caddy provides TLS for back, with HTTP redirected to HTTPS and HSTS.
  - Front sends a CSP that allows the Spotify embed frame and iFrame API script, deployed first in report-only mode. It also sends HSTS, nosniff, a strict referrer policy, frame-ancestors 'none', and a restrictive Permissions-Policy.
  - The database port is never exposed outside the Docker network.
- **Backups:** the VPS provider's automatic snapshots.

### CI and tooling

- GitHub Actions runs lint, type checks, tests, the OpenAPI drift check, gitleaks, `pnpm audit`, `pip-audit` and Trivy on the images. Dependabot opens updates weekly.
- **back:** Python 3.13, `uv`, `ruff` (including the SQL-injection rule), `mypy`, `pytest`.
- **front:** Vitest and Playwright.

## Testing Decisions

- **What makes a good test here:** it exercises timbre through a real entry point (an HTTP endpoint, a job as the queue would run it, a database login, or the browser) and asserts on what an outside observer sees: responses, rows in the database, what the page shows. Tests never reach into private functions, mock internal modules, or assert on how something was computed. A test that passes after a correct refactor and fails after a real bug is the target.
- **Real end-to-end:** tests run against the real stack, with no mocks of timbre's own parts: real Postgres with pgvector, the real e5 model, the real API, the real worker. The only stand-ins are a fixed seed Catalog of well-known Songs with ISRCs (replacing the hours-long import), and recorded HTTP responses for the open-data APIs in import job tests. The browser end-to-end suite uses the real Spotify API and Embed, with credentials as CI secrets.
- **Seam 1, the back HTTP API (main seam):**
  - Search returns Matches with a correct count and order.
  - The cutoff excludes non-fitting Songs, and nonsense input returns zero Matches.
  - N is capped at 60, and paging works.
  - Validation rejects empty and over-long Descriptions and bad parameters.
  - Requests without the front token are rejected.
  - Rate limits return 429.
  - Feedback upserts, switches and withdraws a vote.
  - Preview lookups return availability, cache found and not-found entries with a TTL, never cache errors, and back off on 429.
- **Seam 2, worker jobs:**
  - Import (with recorded open-data responses) produces only Songs with an ISRC and AcousticBrainz data, and resumes after interruption.
  - Build vectors fills vectors for new Songs.
  - Train → evaluate → promote promotes a better model and refuses a worse one.
  - Cache cleanup removes only expired entries.
- **Seam 3, database roles (guards ADR 0001 and RLS):**
  - Connecting as `ml_worker` and as `api_search`, any read of the preview schema fails.
  - Connecting as `api_preview`, any read of catalog or feedback fails.
  - Each role can do exactly its allowed operations, and nothing more.
- **Seam 4, browser end-to-end (Playwright, full stack, real Spotify), run at phone (375 px), tablet (768 px) and desktop (1440 px) widths:**
  - The home page shows sample Descriptions before any search.
  - Typing a Description and submitting shows the count and a grid. N matches the viewport, there is no horizontal scroll, and the column count fits the width.
  - "Carregar mais" adds the next page.
  - Clicking Preview on an available Song opens the docked Spotify player and plays it.
  - Voting 👍 highlights it, pressing 👍 again withdraws it, and voting 👎 highlights 👎. Each state survives a page reload.
  - A nonsense Description (random letters) shows "Nenhuma música encontrada" with samples. Clicking a sample fills the input and shows Matches in one click.
  - Theme toggle switches Light and Dark, the choice persists across reloads, and there is no wrong-theme flash.
  - The page passes an automated accessibility check (axe) in both themes.
- **Pure-function unit tests (Vitest):** the screen-to-N calculation, and the waveform state → target-parameters mapping (including reduced motion). These are the only unit-level tests, because their output is observable behaviour that the browser test can't pin down precisely.
- **Not tested automatically:** the rendered WebGL visuals themselves.
- **Prior art:** none. The repository has no tests yet, so these suites set the patterns.

## Out of Scope

- User accounts, login, saved searches or history.
- Using any Spotify data for matching, ranking, training, evaluation or visuals (ADR 0001), including Audio Features and Spotify-provided artwork.
- Building the Catalog from full data dumps (only when the project owner asks; ADR 0002).
- Fine-tuning the e5 model itself, and GPU training.
- Online (per-vote) model updates.
- Using Preview clicks as a training signal.
- Languages other than Portuguese and English for Descriptions. A UI in languages other than pt-BR (the e2e tests assert pt-BR labels and would need updating).
- Embedding a player in every card. Preview via the deprecated 30-second preview URL.
- Album artwork on cards.
- Column-level encryption, encrypted database connections inside the Docker network, and custom backup tooling beyond provider snapshots.
- Extended quota mode for the Spotify app.
- A Song-language preference next to the search box (for example "qualquer idioma / músicas em inglês / músicas em português"). This could come later. For now, no language quota or filter is applied to Songs.

## Further Notes

- **Decision records:**
  - ADR 0001: Spotify is used only for Preview.
  - ADR 0002: the Catalog is built through the APIs, not the dumps.
  - ADR 0003: Radix UI and Lucide.
- **Research:** the Spotify platform terms and the open music data sources each have a research doc. Both were checked against primary sources on 2026-10-28.
- **Glossary:** all terms used here (Description, Song, Catalog, Fit, Match, Popularity, Preview, Feedback, Benchmark) are defined in the glossary at the repository root.
- **Known risks:**
  - Spotify Developer Policy III.5 ("integrated with content from another service") is broadly worded.
  - Running a public site in development mode is not explicitly addressed by Spotify.
  - AcousticBrainz labels are frozen since 2022 and of limited quality. This is why the own model and the Benchmark matter.
- The project owner has Spotify Premium, which development mode requires for the app owner.
- gitleaks still needs to be installed locally.
- Feedback is the only data that cannot be rebuilt. It is protected by provider snapshots.
