# 11: Waveform background

**What to build:** a subtle animated ribbon of particles behind the page, with depth of field, in the style of the owner's reference image. It responds only to the visitor's own actions (typing, submitting, Matches appearing, Preview playing or stopped) and never pulls attention from the UI.

**Blocked by:** 07, 10

**Status:** ready-for-agent

- [ ] Raw WebGL2, with no 3D library. A ribbon of roughly 20–40k points is shaped by waves in a vertex shader. Depth of field is faked with point size and transparency by depth, plus a few drifting bokeh sprites. It stays low in contrast in both themes.
- [ ] All colours come from one palette configuration, per theme and per state, derived from the app's theme colours (Light and Dark), not from the reference image. The reference image sets only the shape and feel. The look changes by editing that one place.
- [ ] A pure function maps (state, theme, reduced-motion) to target shader parameters, and Vitest covers it. The states:
  - **idle:** slow drift, cool colours;
  - **typing:** a brightness ripple per keystroke, driven by one timestamp per keystroke;
  - **submitting:** the ribbon tightens and lines up horizontally;
  - **results shown:** the ribbon relaxes;
  - **Preview playing:** warmer colours, higher amplitude;
  - **Preview stopped:** eases back over about 2 s to the Matches shape if Matches are on screen, and to idle otherwise.
- [ ] State changes are smooth blends. The play and stop signals come only from the iFrame API's play/pause events (ADR 0001): never position, duration, artwork or audio.
- [ ] With `prefers-reduced-motion`, the ribbon is static and only colours change between states. The animation pauses when the tab is hidden.
- [ ] The canvas is decorative: hidden from assistive technology, and it never blocks clicks.

## Requested changes (owner, after Carl's re-review)

- [ ] **Warm theme token:** add a warm colour token to the theme (Light and Dark) and use it for the Preview playing state, so playing reads clearly warmer than idle.
- [ ] **Light theme particles:** colour the Light theme particles with the theme colours, as Dark does. The Light ribbon is too bright now.
- [ ] **All particles move:** the larger, static particles away from the centre (bokeh/out-of-focus ones) also drift, not only the ribbon.
- [ ] **All particles react to playing:** every particle, ribbon and bokeh alike, responds to the Preview playing state (warmer and livelier) and eases back on stop.
- [ ] **Background:** a little more contrast in the background colour, plus a soft dark vignette at low opacity (about 0.1–0.2 alpha, not more).
- [ ] Keep the owner's own tweaks to the waveform particles in `front/components/waveform-background.tsx`. Build on them, don't revert them.
- [ ] **Background as theme tokens:** the page's background gradient and vignette colours are theme tokens in `:root` and `.dark` (`--bg-center`, `--bg-mid`, `--bg-mid-at`, `--bg-edge`, `--vignette`), holding the owner's navy (Dark) and grey (Light) values; one `body` rule draws them.
- [ ] **Readable text over the new look (owner decision):** keep the particles, bokeh, vignette and glass as they are; the small note under the search panel and the footer credits (text and links) use the full `foreground` colour instead of `muted-foreground`, so they reach WCAG AA (4.5:1) in both themes, in every browser, with a Preview playing.

## Comments

- Review (Carl): Standards 0 hard, all judgement calls (worst: the waveform state is named `results`, but CONTEXT.md says "Match"; the shader parameter list is copied by hand in four places); Spec 1 bug, 2 partial, 1 to ask (worst: a new search while a Preview plays drops the warm "playing" state and a later pause is ignored).
- Review (Carl, re-review): previous findings all fixed. Standards 0 hard, 3 judgement (worst: shader uniforms are matched to TS keys by name only, so a renamed key silently stops working); Spec 0 missing, 0 wrong, 1 open (worst: "Preview playing: warmer colours" is hardly warmer, because the theme mauve is nearly grey; needs the owner to look).
- Review (Carl, round 3, owner's requested changes): Standards 1 hard, 2 judgement (worst: background gradient and vignette use raw hex outside the theme tokens, leaving the body gradient classes in layout.tsx dead); Spec 6 of 7 done, 1 partial, no regressions (worst: the background swapped the indigo-to-mauve theme for neutral navy/grey hex values).
- Review (Carl, round 4 re-review): previous findings all fixed. Standards 0 hard, 1 note (worst: the template's `bg-background` on body is now always overridden by the token body rule, harmless); Spec 0 missing, 0 wrong, no regressions.
