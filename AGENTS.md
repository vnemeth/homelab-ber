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
- **Pin image versions** to a specific tag rather than `latest`, so upgrades are deliberate.
- **Mind the resources.** The host has 8 GB RAM and 256 GB disk shared by all stacks and the
  desktop. Prefer lightweight images, and call out services that are memory- or disk-heavy.
- **Keep the README in sync.** When adding, removing, or changing a stack, update the
  *Stacks* table in `README.md`. When a change involves host-level configuration (packages,
  network, mounts, users), record it in the README's *Setup log*.
- **Avoid port clashes.** Check the *Stacks* table for ports already in use before
  assigning a new one.
- Set `restart: unless-stopped` on long-running services.

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
