# 01: Move the app into front/ and switch to Radix + Lucide

**What to build:** the current timbre page, looking and behaving exactly as it does today, now lives in its own `front` part of the repository and is built from Radix-based shadcn components with Lucide icons (ADR 0003). The repository root keeps no JavaScript tooling of its own.

**Blocked by:** None (can start immediately)

**Status:** resolved

- [x] The Next.js app and everything it owns live under `front`: package manifest, lockfile, pnpm workspace file (keeping its build allowlist), Next, TypeScript, ESLint and shadcn config, the app folder and the components. The repository root has no JS manifest.
- [x] Button, Input, Card and Field are regenerated in shadcn's `radix-lyra` style with `lucide` as the icon library. If that style doesn't exist in the registry, the closest Radix style is used, and the owner sees before/after screenshots before the ticket closes.
- [x] `@base-ui/react` and `@phosphor-icons/react` are removed. The shadcn config names the Radix style and Lucide.
- [x] The page is visually and functionally the same: the title, the search input (named `q`, labelled, required, max 300 characters) and the "Pesquisar" submit button, inside a form.
- [x] Lint, type check and production build pass inside `front`.
- [x] README and `CLAUDE.md` describe how to run the front from its new place.

## Comments

- 2026-10-28, implemented by Bob and reviewed against standards and spec, committed by the owner in 5cf0be1. `radix-lyra` existed in the registry, so no fallback was needed; before/after screenshots were byte-identical. The owner decided: the root `.env` stays until ticket 02, `lucide-react` is installed now, and Card and Field stay trimmed to the parts in use. Also added in review: Prettier 3.9.10 (exact) with `pnpm format` and `front/.prettierignore`, and `.gitignore` patterns anchored to `/front/`. Not covered: an automated page test (Vitest arrives in ticket 03).
