# 17: Preview plays on the first click in Firefox and Safari

**What to build:** in Firefox and Safari (desktop and iPhone), pressing a card's "Prévia" button plays the track, as it already does in Chromium. Today both load the docked Spotify Embed with the right track, but the programmatic `play()` is blocked by their autoplay policies (Firefox also ignores the iframe's `allow="autoplay"`), so the user must click play a second time inside the embed. Found by the new Playwright projects: `e2e/preview.spec.ts` fails in `firefox`, `webkit` and `mobile-safari` at every width, because `data-paused` stays `true` (1440px in Firefox sometimes passes by luck).

**Blocked by:** 07

**Status:** resolved

- [x] Research first: what Spotify's iFrame API supports for Firefox and Safari (for example, creating the controller inside the click handler so the user activation still counts, or showing the embed's own play button as the fallback). Record the finding under `docs/research/`.
- [x] One click on "Prévia" either plays in Firefox and Safari, or the dock clearly asks for the one extra click (pt-BR copy), whichever the research shows is possible.
- [x] `e2e/preview.spec.ts` runs in every Playwright project again (remove its `test.fixme`).

## Comments

Review (Carl): spec met and no standards breaks; fix the Firefox e2e (accept playing or the prompt, as the research says) and the live region hidden by `empty:hidden`; add `pointer-events-none` to the prompt; the rest are nits.

CI run 44299194818 (Bob): WebKit and mobile Safari never showed the prompt. The cause is in the embed code: it posts `ready` once per loaded document, after `createController` has called back, so the listener was never late. It posts `playback_started` as soon as the player has the track loaded (`hasContext`), even when the browser blocks the audio. The dock treated `playback_started` as "playing" and cleared the 2 s prompt timer, so nothing was left to show the prompt while `data-paused` stayed `true`. Fix: `playback_started` only records the URI, and only `playback_update` with `isPaused: false` hides the prompt. The research's step 2 (clear on `playback_started`) was wrong on this point. Firefox keeps `data-paused="false"` after the dock closes: still open. Reading the code can't tell whether `pause()` doesn't reach the hidden iframe or whether the embed doesn't report the pause, so this needs the CI traces, which are now uploaded on failure.

Firefox fix (Bob, the user chose "unload on close"): `close()` now calls the controller's `destroy()` (Spotify's script removes the iframe and its `message` listener). It also drops the controller and sets `playing` to paused locally, which holds by construction now that the iframe is gone. A player still being created is destroyed as soon as it exists. The next Prévia builds a new player through the first-click path. The close tests now assert that no embed iframe is left. The logo test also goes back to the results and checks that Prévia plays again in one new player. Also corrected: `loadUri` reloads the embed even for the same track (Spotify never sets `currentUri`), so the `loadedUri` re-arm was redundant and is gone, and the research note says this now.

Review (Carl, CI 44299194818 fixes): close/destroy/rebuild is race-safe and the tests can't pass on a silent player; fix the research doc, which still says to hide the prompt on `playback_started` (steps 4 and 2), and consider having the 2 s timer check `paused` when it fires instead of being cancelled by one `isPaused: false` event; a failed script load still leaves Prévia dead until the dock closes (the `.catch` never runs); the rest are nits.
