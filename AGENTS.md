# AGENTS.md

Guidance for AI coding agents working in this repository.

## What this repo is

Configuration for a single-node homelab in Berlin:

- **Host:** Lenovo ThinkCentre M80q Gen 3, 8 GB RAM, 256 GB SSD
- **OS:** Minimal Debian with a lightweight Xfce desktop
- **Services:** All run in Docker, defined as Docker Compose stacks managed by Dockge

`README.md` is the source of truth for the server configuration. Read it before making changes.

## Layout

- `README.md` — hardware, OS, network, setup log, and the list of stacks.
- `stacks/<stack-name>/` — one folder per Dockge stack:
  - `compose.yaml` — the Compose definition (Dockge's default file name)
  - `.env.example` — template of the stack's environment variables with placeholder values,
    if the stack needs any. The real `.env` lives only on the server and is git-ignored.

## Conventions

- **One service (or tightly coupled group) per stack.** Folder names are lowercase and
  hyphenated, and match the Dockge stack name.
- **Use image tags that follow one version line**, e.g. `traefik:v3`, `louislam/dockge:1`,
  `postgres:16-alpine`. Updates within that line come in through Dockge's *Update* button;
  moving to a new major version (or, for apps that require stepwise upgrades like
  authentik, a new release) is a deliberate tag change. Never use `latest`, and never let
  a database image float across major versions.
- **Mind the resources.** The host has 8 GB RAM and 256 GB disk shared by all stacks and the
  desktop. Prefer lightweight images, and call out services that are memory- or disk-heavy.
- **Keep the README in sync.** When adding, removing, or changing a stack, update the
  *Stacks* table in `README.md`. When a change involves host-level configuration (packages,
  network, mounts, users), record it in the README's *Setup log*.
- **Avoid port clashes.** Check the *Stacks* table for ports already in use before
  assigning a new one.
- Set `restart: unless-stopped` on long-running services.
- **Web interfaces go through Traefik.** A stack with a web UI joins the external `proxy`
  network and sets these labels, instead of publishing a port:
  ```yaml
  labels:
    - traefik.enable=true
    - traefik.http.routers.<name>.rule=Host(`<name>.local.ber.nvcode.com`)
    - traefik.http.routers.<name>.entrypoints=websecure
    - traefik.http.services.<name>.loadbalancer.server.port=<container port>
  ```
  The `websecure` entrypoint applies the `*.local.ber.nvcode.com` wildcard certificate, so
  routers don't set TLS options themselves.
- **Protect web interfaces with authentik.** Add
  `traefik.http.routers.<name>.middlewares=authentik@docker` to the router, unless the app
  supports OIDC itself (then ask the user which to use). Never add it to authentik's own
  router.
- **Each new hostname needs a DNS record.** The user adds a CNAME
  `<name>.local.ber.nvcode.com` → `lab.local.ber.nvcode.com` at DreamHost. Remind them, and
  add it to the DNS table in `README.md`.

## Secrets

- Never commit real passwords, API keys, or tokens. `.env` files are git-ignored.
- Every variable a stack's `compose.yaml` reads from `.env` must be listed in that stack's
  `.env.example`, with a placeholder value (e.g. `changeme`) and a short comment where the
  purpose isn't obvious.
- Keep `.env.example` in sync when adding, renaming, or removing variables.

## Working style

- This setup is built incrementally. Only add what is asked for; don't scaffold stacks or
  README sections ahead of time.
- Changes here are applied on the server by the user. Don't assume anything has been
  deployed unless the user says so.
