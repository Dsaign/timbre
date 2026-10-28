# 10: Themes, frosted glass and footer

**What to build:** the visitor gets Light and Dark themes that follow the system by default, with a toggle that is remembered and never flashes the wrong theme. Panels are frosted glass that stays readable. The footer credits the data sources and links to the public repository.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] `next-themes` follows the system by default and has a Lucide sun/moon toggle. The choice is stored in local storage (no cookie), and there is no wrong-theme flash on load.
- [ ] Real backdrop blur only on the search panel, the docked player surface (styled when ticket 07's player exists) and one shared panel behind the grid. Cards use a more opaque tint with little or no blur.
- [ ] `prefers-reduced-transparency` switches these to solid surfaces. Text meets WCAG AA contrast in both themes.
- [ ] Footer: credits MusicBrainz, AcousticBrainz, ListenBrainz and Spotify, plus the official GitHub mark (SVG, not a Lucide icon) linking to https://github.com/Dsaign/timbre.
- [ ] Playwright: the toggle switches the theme, the choice persists across reloads, and the page loads without a wrong-theme flash. axe finds no violations in either theme.
