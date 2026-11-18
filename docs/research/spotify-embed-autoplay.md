# Spotify Embed autoplay: one click in Firefox and Safari?

Researched 2026-11-18 for ticket 17 (`.scratch/*/issues/17-preview-autoplay-firefox-safari.md`). Primary sources only: Spotify's docs and its shipped iFrame API script, the HTML spec, MDN, and Gecko and WebKit source on their `main` branches that day. Nothing was run in a browser.

## Summary verdict

1. **Safari (macOS and iOS): NO, not with the Spotify iFrame API as timbre uses it.** Every `loadUri()` of a new track navigates the iframe to a new document. Spotify's script holds `play()` in a queue until that document reports `ready`, then sends it by `postMessage` from a `setTimeout`. By then no user gesture is left. WebKit forwards a gesture through `postMessage` only when the message is posted *during* the gesture and arrives within 1 s, and it never hands a parent click to a cross-origin child.
2. **Firefox: UNCLEAR. By the source it should already work.** Gecko's default policy allows audible playback in any frame once the *top-level* page has sticky activation, meaning any earlier click on timbre, with no time limit. `allow="autoplay"` plays no part, because Firefox does not implement the `autoplay` Permissions-Policy. The failing Playwright run may be a test-environment artifact (for example, Playwright's Firefox ships with Widevine turned off). Check by hand in a real Firefox before changing code for it.
3. **No confirmed workaround exists.** Spotify's own reference says `play()` "might not be supported in all browsers … Safari blocks autoplay without user interaction". A Spotify engineer on the forum also points people to autoplay restrictions. WebKit has an autoplay quirk for YouTube embeds and none for Spotify.
4. **Recommendation: the fallback.** Keep `loadUri` + `play()` as today. If playback has not started a short time after the embed is `ready`, show a pt-BR prompt beside the dock (not over it), for example "Toque em ▶ no player do Spotify para ouvir". Hide it on `playback_started` or `isPaused === false`. This works by observed behaviour, with no browser sniffing, so it also covers Firefox if (2) turns out to be a real block.
5. **e2e:** in Chromium, assert `data-paused="false"` after one click, as today. In every project, assert that the dock ends up either playing or showing the prompt. In Firefox and WebKit, also click the embed's own play button through `frameLocator` and then assert `data-paused="false"` and that the prompt is gone.

---

## Sources

| Source | URL | Version / date |
|---|---|---|
| iFrame API reference | https://developer.spotify.com/documentation/embeds/references/iframe-api | fetched 2026-11-18, no date shown |
| Using the iFrame API | https://developer.spotify.com/documentation/embeds/tutorials/using-the-iframe-api | fetched 2026-11-18 |
| Embeds troubleshooting | https://developer.spotify.com/documentation/embeds/tutorials/troubleshooting | fetched 2026-11-18 |
| iFrame API loader | https://open.spotify.com/embed/iframe-api/v1 | loads `iframe_api.daf0055e35711eb6aa3a.js` |
| iFrame API implementation | https://embed-cdn.spotifycdn.com/_next/static/iframe_api.daf0055e35711eb6aa3a.js | content hash in the name |
| Spotify forum: "Iframe embedcontroller.play() broken" (Spotify engineer `sushants`) | https://community.spotify.com/forum/en/discussion/5820105/iframe-embedcontroller-play-broken | thread, accepted answer |
| HTML spec, user activation | https://html.spec.whatwg.org/multipage/interaction.html#tracking-user-activation | Living Standard, 2026-11-18 |
| HTML spec, media "allowed to play" | https://html.spec.whatwg.org/multipage/media.html#allowed-to-play | Living Standard, 2026-11-18 |
| MDN Autoplay guide | https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay | fetched 2026-11-18 |
| MDN browser-compat-data, `Permissions-Policy: autoplay` | https://github.com/mdn/browser-compat-data/blob/main/http/headers/Permissions-Policy.json | `main`, 2026-11-18 |
| Gecko `AutoplayPolicy.cpp` | https://github.com/mozilla-firefox/firefox/blob/4c24f734d8214b601bab49ad4df00ccc45fdbe4d/dom/media/autoplay/AutoplayPolicy.cpp | commit `4c24f734` |
| Gecko `StaticPrefList.yaml` (`media.autoplay.*`) | https://github.com/mozilla-firefox/firefox/blob/4c24f734d8214b601bab49ad4df00ccc45fdbe4d/modules/libpref/init/StaticPrefList.yaml | commit `4c24f734` |
| Gecko `FeaturePolicyUtils.cpp` | https://github.com/mozilla-firefox/firefox/blob/4c24f734d8214b601bab49ad4df00ccc45fdbe4d/dom/security/featurepolicy/FeaturePolicyUtils.cpp | commit `4c24f734` |
| Playwright Firefox prefs | https://github.com/microsoft/playwright/blob/main/browser_patches/firefox/preferences/playwright.cfg | `main`, 2026-11-18 |
| WebKit `LocalDOMWindow.cpp` (postMessage gesture forwarding) | https://github.com/WebKit/WebKit/blob/325310739b619d8f40a1832cbcc242a5137265d5/Source/WebCore/page/LocalDOMWindow.cpp | commit `32531073` |
| WebKit `UserGestureIndicator.h` | https://github.com/WebKit/WebKit/blob/325310739b619d8f40a1832cbcc242a5137265d5/Source/WebCore/dom/UserGestureIndicator.h | commit `32531073` |
| WebKit `MediaElementSession.cpp` | https://github.com/WebKit/WebKit/blob/325310739b619d8f40a1832cbcc242a5137265d5/Source/WebCore/html/MediaElementSession.cpp | commit `32531073` |
| WebKit `Document.cpp` (`mediaUserGestureReason`) | https://github.com/WebKit/WebKit/blob/325310739b619d8f40a1832cbcc242a5137265d5/Source/WebCore/dom/Document.cpp | commit `32531073` |
| WebKit blog: Auto-Play Policy Changes for macOS | https://webkit.org/blog/7734/auto-play-policy-changes-for-macos/ | 2017-06-08 |
| WebKit blog: New video policies for iOS | https://webkit.org/blog/6784/new-video-policies-for-ios/ | 2016 |

---

## 0. What timbre does today (`front/components/preview-player.tsx`)

- **First click:** `play()` runs inside the React `onClick`. It then waits for `loadIframeApi()` (a script loaded over the network) and calls `createController()`. Inside the controller callback it calls `c.play()`. All of that happens seconds after the click, in later tasks.
- **Later click on another card:** `controller.current.then(c => { c.loadUri(uri); c.play() })`. This runs in a microtask right after the click handler.
- **Same card while playing:** `c.togglePlay()` in the same microtask.

## 1. Spotify iFrame API

- `createController(element, options, callback)` replaces `element` with the Embed iframe. Options are `uri`/`url`, `width` and `height`. https://developer.spotify.com/documentation/embeds/references/iframe-api
- The reference lists `loadUri` (kept "for existing integrations"; `loadEntity` is preferred), `play` ("begins playing the content that had been previously loaded"), `pause`, `resume` ("If playback was not started, this method will start playback"), `togglePlay`, `restart`, `seek` and `destroy`. Events: `ready`, `playback_started`, `playback_update` (`isPaused`, `isBuffering`, `position`, `duration`), plus `error`, `enter_fullscreen` and `exit_fullscreen`, which appear in the script only. Same URL.
- Autoplay, quoted from the reference's Notes: "The iFrame API's play method, which starts playback of the Embed player without user interaction, might not be supported in all browsers and for all users. For instance, Safari blocks autoplay without user interaction." No other browser is named. No workaround is given.
- Troubleshooting says Embeds "work best in Chrome, Firefox, Edge, Opera and Safari". It does not mention autoplay. https://developer.spotify.com/documentation/embeds/tutorials/troubleshooting
- **What the shipped script does** (`iframe_api.daf0055e35711eb6aa3a.js`):
  - The iframe gets `allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"` and `loading="lazy"`.
  - `loadUri`/`loadEntity` for a track sets `this.loading = true` and then **`this.iframeElement.src = embedURL`**. That is a full navigation of the iframe to a new cross-origin document. Loading the same URI again returns early.
  - `play`, `togglePlay` and the other controls are `postMessage({command}, '*')`. While `loading` is true they are pushed to `_commandQ`. When the new document posts `ready`, `flushCommandQ()` sends each queued command inside **`setTimeout(…, 0)`**.
  - Inside the embed, the message handler dispatches a state action (`"play"`, `"toggle"`, …) and does not call a media element directly. Whether the actual `HTMLMediaElement.play()` runs synchronously in that handler is **UNCLEAR** (minified code, not traced).
- Spotify forum, accepted answer thread: Spotify engineer `sushants` ("I'm an engineer working on the embed player and the iframe API") answers a later "play() doesn't work" report with "Have you checked whether the issue is with autoplay restrictions being applied?" and links MDN's autoplay guide. No workaround from staff. https://community.spotify.com/forum/en/discussion/5820105/iframe-embedcontroller-play-broken

## 2. Firefox

- **`allow="autoplay"` / Permissions-Policy `autoplay`: not implemented.** browser-compat-data lists `firefox: version_added: false` for `Permissions-Policy: autoplay`. `FeaturePolicyUtils.cpp` has no `autoplay` feature. So the attribute is ignored, as the ticket says.
- **The policy that does apply** (`AutoplayPolicy.cpp`, default `media.autoplay.blocking_policy = 0` = "sticky activation", `media.autoplay.default = 1` = blocked audible):
  - `IsWindowAllowedToPlayByUserGesture` reads `aWindow->GetBrowsingContext()->GetTopWindowContext()->HasBeenUserGestureActivated()`. It logs "Allow autoplay as top-level context has been activated by user gesture."
  - So a media element in **any** frame, cross-origin included, may play audibly once the **top-level page** has been clicked at any time. There is no transient window and no need to call from inside the handler.
- `browser/app/profile/firefox.js` does not override either pref.
- MDN says the default of `media.autoplay.default` is `0`. The source says `1`. The source is authoritative, and MDN's statement is outdated on that point.
- **UNCLEAR: why the Firefox e2e fails.** By the code above, real Firefox should play timbre's preview after the click. Candidates, none verified:
  - (a) Playwright's Firefox turns off Widevine (`playwright.cfg`: "Disable download and usage of OpenH264: and Widevine plugins"), and the Embed may need EME.
  - (b) Playwright's synthesized click may not mark the top `WindowContext` as activated.
  - (c) Spotify's embed may refuse on its own logic.
  - Check by hand in a stock Firefox first.

## 3. Safari / WebKit (macOS and iOS)

- Policy: "Websites should assume any use of `<video>` or `<audio>` requires a user gesture click to play." https://webkit.org/blog/7734/auto-play-policy-changes-for-macos/
- iOS: the call to `play()` "must have directly resulted from a handler for a `touchend`, `click`, `doubleclick`, or `keydown` event". https://webkit.org/blog/6784/new-video-policies-for-ios/
- `allow="autoplay"`: Safari has no `Permissions-Policy: autoplay` (browser-compat-data `safari: version_added: false`). It supports `iframe allow` in general from 11.1.
- **What counts as a gesture for media in the iframe** (`Document::mediaUserGestureReason`): either `UserGestureIndicator::processingUserGestureForMedia()` (an active gesture token) or the **iframe's own window** having transient activation. A parent click gives a cross-origin child no activation (see §4).
- **postMessage does carry a gesture, briefly.** `LocalDOMWindow::processPostMessage` captures `UserGestureIndicator::currentUserGesture()` when the message is *posted*. On delivery it re-installs that token unless it is older than `maximumIntervalForUserGestureForwarding = 1_s` ("One second matches Gecko"). The same holds across processes (`postMessageFromRemoteFrame`).
- **Why this does not save timbre:**
  - The first click posts `play` seconds later.
  - A click on another card calls `loadUri`, which navigates the iframe, so Spotify queues `play` and posts it from `setTimeout` after the new document's `ready`. That is outside any gesture.
  - Only `togglePlay` on the already-loaded track is posted inside the click: React `onClick` plus a microtask. Whether WebKit still counts that microtask as inside the gesture is **UNCLEAR, leaning yes**. Even then, whether Spotify's embed calls `audio.play()` while the token is active is **UNCLEAR** (§1).
- WebKit carries a `needsYouTubeEmbedAutoplayQuirk` in `MediaElementSession::playbackStateChangePermitted`. It has no Spotify equivalent.

## 4. HTML spec: transient activation

- Duration: an implementation-defined constant, "expected be at most a few seconds". https://html.spec.whatwg.org/multipage/interaction.html#transient-activation-duration
- Propagation: activation notification sets the timestamp on the clicked document's window, **all ancestor** windows, and descendant windows "filtered to include only those navigables whose active document's origin is same origin". So a click on timbre's button **does not** activate the cross-origin `open.spotify.com` iframe. A click inside the iframe does activate timbre. https://html.spec.whatwg.org/multipage/interaction.html#activation-notification
- Sticky activation is "carried over between windows for same-origin navigations" only. The iframe's navigation to a new Spotify document after `loadUri` keeps nothing from timbre.
- Media: "a user agent could allow playback only when the media element's Window object has transient activation". This is the element's own window, not the parent's. https://html.spec.whatwg.org/multipage/media.html#allowed-to-play
- The spec does not forward activation through `postMessage`. WebKit (and, per its comment, Gecko) does it as an engine extension.

## 5. Workarounds others confirmed

- None found from Spotify staff or in Spotify docs. The reference names Safari as a known limit.
- Ideas checked and rejected:
  - **Create the controller inside the click handler.** It does not help: the iframe document loads later, and `play` is queued until `ready`.
  - **Call `play()` synchronously in the handler.** It only helps when no `loadUri` is needed (same track), and it is UNCLEAR even then.
  - **One preloaded Embed per card, so `play()` needs no navigation.** It is UNCLEAR whether Spotify's player keeps the forwarded gesture. It also breaks ADR 0001's single docked Embed and loads N iframes. Not recommended.
  - **`navigator.getAutoplayPolicy()`.** It cannot be queried for a cross-origin iframe's document, so it is not usable here.

## 6. Recommendation

**Fallback, smallest change:**

1. Keep `loadUri` + `play()`. Chromium plays as today, and so may Firefox (§2).
2. In `PreviewPlayer`, mark the request as pending when "Prévia" is pressed. Clear the flag on `playback_started` or `playback_update` with `isPaused === false`.
3. If the request is still pending a short grace period after the controller's `ready` event, show one pt-BR line next to the dock. The figure of ~2 s is a guess to tune. Example copy: "Toque em ▶ no player do Spotify para ouvir". Render it in an `aria-live="polite"` region, outside the Embed's box (ADR 0001: nothing drawn over the Embed).
4. Hide the line when playback starts, the dock closes, or another track is requested.
5. Do not detect the browser by user agent. The line appears only where playback really did not start.

**e2e (`e2e/preview.spec.ts`, remove `test.fixme`):**

- All projects: after clicking "Prévia", expect the dock open with the right track. Then expect `data-paused="false"` **or** the prompt to be visible (`getByRole('status')` / its text).
- `chromium`: expect `data-paused="false"` and no prompt, the current behaviour.
- `firefox`, `webkit`, `mobile-safari`:
  - Expect the prompt.
  - Then click the Embed's play button through `page.frameLocator('section[aria-label="Prévia no Spotify"] iframe').getByRole('button', …)`. Spotify's label is **UNCLEAR** and may be localized, so pin it after a first run.
  - Expect `data-paused="false"` and the prompt hidden.
- Keep tests silent: headless Playwright plus the existing mute setup. Per project rule, these run in CI only.

## Open risks

- The Firefox root cause is unverified (§2). If real Firefox plays, the prompt never shows there, and only the Playwright project needs the fallback branch.
- Spotify may change the iframe-API internals (queue plus `setTimeout`) without notice. The prompt logic depends only on documented events.
- The Embed button's accessible name, needed for the e2e click, is not documented.
