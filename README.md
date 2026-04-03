# c5 — container claude code chrome control

Run Claude Code inside a Docker container while controlling Chrome on your host machine.

Python port of [claude-code-remote-chrome](https://github.com/badlogic/claude-code-remote-chrome).

## What it does

Claude Code has a "Claude in Chrome" feature that lets it control your browser — navigate pages, fill forms, take screenshots, etc. Normally this only works when Claude Code runs directly on your machine. This project bridges that gap so Claude Code running in a container can talk to Chrome on your host.

## How it works

A Python bridge in the container and a Python script on the host forward messages between them:

```
Container                          Host
Claude Code                        Chrome
    |                                |
    v                                ^
bridge_container.py  --TCP:9229-->  bridge_host.py
(Unix socket)                      (Unix socket)
```

## Prerequisites

- Docker (Docker Desktop, OrbStack, or similar)
- Python 3.8+ on the host (for bridge_host.py)
- Chrome with the [Claude browser extension](https://claude.ai/chrome) installed
- Claude account credentials

## Setup

1. **Create `.env.local`** with your credentials:

   ```
   CLAUDE_CREDENTIALS={"claudeAiOauth":{"accessToken":"...","refreshToken":"...","expiresAt":...}}
   ```

   You can find these in `~/.claude/.credentials.json` on your host.

2. **Build and start** the container:

   ```bash
   make up
   ```

3. **Start the host bridge** (separate terminal):

   ```bash
   python3 bridge_host.py
   ```

4. **Inside the container**, start Claude (the bridge starts automatically via entrypoint):

   ```bash
   claude --chrome
   ```

5. Ask Claude to do something in Chrome, e.g. `open google.com`.

## Commands

| Command      | Description                              |
|-------------|------------------------------------------|
| `make up`   | Build image and start interactive shell  |
| `make shell`| Open additional terminal in the container |

## Files

| File | Location | Purpose |
|------|----------|---------|
| `bridge_host.py` | Host | TCP server, connects to real NMH socket |
| `bridge_container.py` | Container | Unix socket listener, forwards to TCP host bridge |
| `chrome_native_host.py` | Container | Placeholder NMH (Claude Code expects it; MCP doesn't use it) |
| `entrypoint.sh` | Container | Credentials, chrome-native-host, starts bridge_container.py |
| `Dockerfile` | Build | node:20-slim + python3, Claude CLI, user matching host UID |
| `docker-compose.yml` | Build | Sets env vars |
| `Makefile` | Host | `up`, `shell` commands |

## Troubleshooting

- **"Extension not detected"** — Make sure `bridge_host.py` is running on the host and Chrome has the Claude extension active.
- **Bridge container can't connect** — Verify `bridge_host.py` is listening on port 9229.
- **Username mismatch** — The `USER` env var in the container must match the socket directory name. It defaults to `claude`.
