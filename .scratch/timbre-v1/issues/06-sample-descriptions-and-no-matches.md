# 06: Sample Descriptions and the no-Matches state

**What to build:** before searching, the visitor sees clickable sample Descriptions that show what timbre understands. A search with no Matches says so clearly and offers the same samples. Clicking a sample fills the search box and runs the search in one click.

**Blocked by:** 04

**Status:** ready-for-agent

- [ ] The six owner-approved sample Descriptions, shown as clickable chips on the empty home page:
  1. violão calmo para estudar
  2. guitarra suja e voz rouca, clima de estrada à noite
  3. something dark and electronic to focus
  4. músicas alegres e dançantes para uma festa
  5. sad piano ballad, slow and quiet
  6. rock pesado e agressivo com bateria forte
- [ ] When a search has zero Matches, the page shows "Nenhuma música encontrada" and the same chips.
- [ ] Clicking a chip fills the input with that Description and runs the search in one action.
- [ ] The chips are keyboard-reachable and labelled.
- [ ] Playwright: a nonsense Description (random letters) shows the no-Matches state. Clicking a chip fills the input and shows Matches.
