#!/usr/bin/env bash
# Fails when the committed back/openapi.json or front/lib/api/schema.d.ts no longer match the API code.
# Fix with: (cd back && uv run python -m timbre_back.openapi > openapi.json) && (cd front && pnpm api:types)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

(cd "$root/back" && uv run --locked python -m timbre_back.openapi) > "$tmp/openapi.json"
diff -u "$root/back/openapi.json" "$tmp/openapi.json"
(cd "$root/front" && pnpm exec openapi-typescript "$tmp/openapi.json" -o "$tmp/schema.d.ts" > /dev/null)
diff -u "$root/front/lib/api/schema.d.ts" "$tmp/schema.d.ts"
echo "OpenAPI spec and generated TS types are current."
