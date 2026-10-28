# 11: Waveform background

**What to build:** a subtle animated ribbon of particles behind the page, with depth of field, in the style of the owner's reference image. It responds only to the visitor's own actions (typing, submitting, Matches appearing, Preview playing or stopped) and never pulls attention from the UI.

**Blocked by:** 07, 10

**Status:** ready-for-agent

- [ ] Raw WebGL2, with no 3D library. A ribbon of roughly 20–40k points is shaped by waves in a vertex shader. Depth of field is faked with point size and transparency by depth, plus a few drifting bokeh sprites. It stays low in contrast in both themes.
- [ ] All colours come from one palette configuration, per theme (Dark: deep navy/teal with a cyan ribbon and warm edge; Light: pale mist with a deeper teal/indigo ribbon and soft grey bokeh) and per state. The look changes by editing that one place.
- [ ] A pure function maps (state, theme, reduced-motion) to target shader parameters, and Vitest covers it. The states:
  - **idle:** slow drift, cool colours;
  - **typing:** a brightness ripple per keystroke, driven by one timestamp per keystroke;
  - **submitting:** the ribbon tightens and lines up horizontally;
  - **results shown:** the ribbon relaxes;
  - **Preview playing:** warmer colours, higher amplitude;
  - **Preview stopped:** eases back to idle over about 2 s.
- [ ] State changes are smooth blends. The play and stop signals come only from the iFrame API's play/pause events (ADR 0001): never position, duration, artwork or audio.
- [ ] With `prefers-reduced-motion`, the ribbon is static and only colours change between states. The animation pauses when the tab is hidden.
- [ ] The canvas is decorative: hidden from assistive technology, and it never blocks clicks.
