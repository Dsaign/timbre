# timbre

Describe a song you like and get music recommendations. Early stage: the search form exists, the recommendation logic does not yet.

The Next.js 16 app lives in `front/`. Run every command below from there.

## Run

```bash
cd front
pnpm install
pnpm dev
```

Open http://localhost:3000.

## Check

```bash
cd front
pnpm lint
pnpm exec tsc --noEmit   # needs the route types: run `pnpm build` or `pnpm dev` once first
pnpm build
pnpm format   # Prettier, rewrites files in place
```
