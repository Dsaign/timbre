# 17: Preview plays on the first click in Firefox and Safari

**What to build:** in Firefox and Safari (desktop and iPhone), pressing a card's "Prévia" button plays the track, as it already does in Chromium. Today both load the docked Spotify Embed with the right track, but the programmatic `play()` is blocked by their autoplay policies (Firefox also ignores the iframe's `allow="autoplay"`), so the user must click play a second time inside the embed. Found by the new Playwright projects: `e2e/preview.spec.ts` fails in `firefox`, `webkit` and `mobile-safari` at every width, because `data-paused` stays `true` (1440px in Firefox sometimes passes by luck).

**Blocked by:** 07

**Status:** needs-triage

- [ ] Research first: what Spotify's iFrame API supports for Firefox and Safari (for example, creating the controller inside the click handler so the user activation still counts, or showing the embed's own play button as the fallback). Record the finding under `docs/research/`.
- [ ] One click on "Prévia" either plays in Firefox and Safari, or the dock clearly asks for the one extra click (pt-BR copy), whichever the research shows is possible.
- [ ] `e2e/preview.spec.ts` runs in every Playwright project again (remove its `test.fixme`).
