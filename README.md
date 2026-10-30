# homelab-ber

Configuration for my Berlin homelab. This README describes the server itself and is
updated as the setup evolves. Service definitions live in [`stacks/`](stacks/).

## Hardware

| Component | Details                       |
| --------- | ----------------------------- |
| Model     | Lenovo ThinkCentre M80q Gen 3 |
| RAM       | 8 GB                          |
| Storage   | 256 GB SSD                    |

## Operating system

- Minimal Debian installation
- Lightweight Xfce desktop
- Hostname: _TBD_
- Debian version: _TBD_

## Network

_TBD_ — static IP, DNS, remote access, etc.

## Container platform

- All services run in Docker containers.
- Docker Compose stacks are managed with [Dockge](https://github.com/louislam/dockge).
- Each stack is a folder under [`stacks/`](stacks/) containing a `compose.yaml` and,
  where needed, a `.env.example`. To deploy, copy it to `.env` on the server and fill in
  the real values. `.env` files are git-ignored and never committed.

## Repository layout

```
.
├── .gitignore    # Keeps real .env files out of git
├── README.md     # Server configuration (this file)
├── AGENTS.md     # Instructions for AI coding agents working in this repo
└── stacks/       # One folder per Docker Compose stack, managed by Dockge
```

## Stacks

| Stack | Purpose | Port(s) | Notes |
| ----- | ------- | ------- | ----- |
| _none yet_ |    |         |       |

## Setup log

Steps performed on the server, in order. Append new entries as they happen.

1. _TBD_
