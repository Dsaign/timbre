## Conventions

- UI primitives: Radix UI (through shadcn components). Icons: Lucide (`lucide-react`). Brand logos use the official SVGs. See `docs/adr/0003-radix-ui-and-lucide-icons.md`.

## Agent skills

### Issue tracker

Issues and specs are local markdown files under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default triage labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
