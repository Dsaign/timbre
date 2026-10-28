# 05: Screen-sized grid and "carregar mais"

**What to build:** the grid shows exactly as many Matches as fit the visitor's screen. "Carregar mais" adds the next set. On any screen size the layout adapts without sideways scrolling and without reloading.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] On submit, client code measures how many cards fit (columns × visible rows) and adds `n` to the URL. Without JavaScript, `n` is 24. The server caps `n` at 60.
- [ ] The URL holds only `q` and `n`. "Carregar mais" adds the next page without changing the URL, and a reload or shared link shows page 1.
- [ ] Resizing or rotating only reflows the layout on the client. No new request is made.
- [ ] Vitest covers the screen-to-N calculation.
- [ ] Playwright at 375, 768 and 1440 px checks: no horizontal scroll, `n` matches the viewport, the column count fits the width, and "carregar mais" appends the next page.
