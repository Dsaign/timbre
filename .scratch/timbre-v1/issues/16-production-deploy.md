# 16: Production deploy

**What to build:** timbre is live on the internet. The front is on Vercel, and the back end runs on a small VPS with HTTPS and automatic snapshots. Every secret is in the right place, and nothing is left in development mode by accident. An agent generates a `/wizard` script that walks the owner through the steps only a human can do (buying the VPS, DNS, the Vercel project, secrets).

**Blocked by:** 03, 09

**Status:** ready-for-human

- [ ] The VPS runs the Compose stack behind Caddy, with automatic TLS, HTTP → HTTPS redirects and HSTS. The database port is not exposed.
- [ ] The provider's automatic snapshots are switched on.
- [ ] The Vercel project uses `front` as its root directory. Its env vars hold the front→back token and the back URL.
- [ ] The VPS `back/.env` is permission-restricted (600) and holds all back secrets. The GitHub Actions secrets for the real-Spotify end-to-end test are present.
- [ ] Interactive API docs are off in production.
- [ ] After one production check with no CSP violations, the CSP switches from Report-Only to enforcing.
- [ ] Both domains are checked on securityheaders.com and the results noted.
