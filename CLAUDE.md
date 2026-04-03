# CLAUDE.md — Technical context for AI agents

## Architecture

Chrome Bridge is a transparent TCP proxy for Chrome Native Messaging Host (NMH) Unix sockets. It enables Claude Code's built-in MCP server (`claude --claude-in-chrome-mcp`) to communicate with Chrome running on the host from inside a Docker container.

### Data flow

```
Claude Code (container)
  → claude --claude-in-chrome-mcp (MCP server, spawned by Claude)
    → connects to Unix socket: /tmp/claude-mcp-browser-bridge-{USER}/{PID}.sock
      → bridge_container.py (entrypoint.sh, forwards to TCP)
        → bridge_host.py (TCP :9229, forwards to real NMH socket)
          → /tmp/claude-mcp-browser-bridge-{host-user}/{NMH-PID}.sock
            → Chrome NMH → Chrome Extension → chrome.debugger API
```

### Protocol

Native Messaging framing on the Unix socket:
- **4 bytes** — message length (uint32, little-endian)
- **N bytes** — JSON payload (UTF-8)

Example command:
```json
{"method":"execute_tool","params":{"client_id":"claude-code","tool":"tabs_context_mcp","args":{"createIfEmpty":true}}}
```

The bridge does raw byte forwarding — no parsing or modification of messages.

### Key discovery: USER env var

Claude Code's MCP server resolves the socket directory name from the `USER` environment variable. Docker does NOT set `$USER` automatically from the Dockerfile `USER` directive. Without `ENV USER=claude` in the Dockerfile, the MCP server looks in `/tmp/claude-mcp-browser-bridge-unknown/` and never finds the bridge socket.

### Key discovery: Unix sockets don't work through OrbStack volume mounts

Socket files appear in `ls` but `connect()` returns `ECONNREFUSED`. This is why the TCP bridge is necessary.

### Key discovery: chrome-native-host is NOT used by MCP

The file `~/.claude/chrome/chrome-native-host` is created by Claude Code for Chrome's `connectNative()` API. The MCP server does NOT spawn it — it directly watches the socket directory. The entrypoint still creates this file because Claude Code expects it to exist.

### Key discovery: socket permissions must be strict

The MCP server requires the socket directory to be `0700` and the socket file to be `0600`. Without this, the MCP server refuses to connect. `bridge_container.py` sets `os.chmod(SOCK_PATH, 0o600)` after binding; the directory is set via `mkdir -m 700`.

### Key discovery: bridge_container.py calls os.setsid()

When `bridge_container.py` runs as a background process in `entrypoint.sh`, Ctrl+C in the container terminal sends SIGINT to the entire process group, killing the bridge. `bridge_container.py` calls `os.setsid()` at startup to move itself to its own session, protecting it from terminal signals. This mirrors the original `setsid socat ...` pattern.

## File overview

| File | Location | Purpose |
|------|----------|---------|
| `bridge_host.py` | Host | TCP server, connects to real NMH socket |
| `bridge_container.py` | Container | Unix socket listener, forwards to TCP host bridge |
| `chrome_native_host.py` | Container | Placeholder NMH binary |
| `entrypoint.sh` | Container | Credentials, chrome-native-host, bridge_container.py |
| `Dockerfile` | Build | node:20-slim + python3, Claude CLI, user matching host UID |
| `docker-compose.yml` | Build | Sets env vars |
| `Makefile` | Host | `up`, `shell` commands |

## Environment variables

| Variable | Where | Default | Purpose |
|----------|-------|---------|---------|
| `USER` | Dockerfile ENV | `claude` | Socket directory name |
| `BRIDGE_PORT` | docker-compose | `9229` | TCP port between bridges |
| `BRIDGE_TCP_HOST` | bridge_container.py | `host.docker.internal` | Host address from container |
| `BRIDGE_USER` | bridge_host.py | current username | Host socket directory name |
| `BRIDGE_HOST` | bridge_host.py | `0.0.0.0` | TCP bind address |
| `BRIDGE_SOCK_PATH` | bridge_container.py | set by entrypoint.sh | Unix socket path to create |
| `CLAUDE_CREDENTIALS` | .env.local | — | OAuth JSON for ~/.claude/.credentials.json |

## Testing

To manually test the bridge from inside the container:

```bash
# 1. Verify bridge_container.py is running and socket exists
ls /tmp/claude-mcp-browser-bridge-claude/

# 2. Test connectivity (requires bridge_host.py running on host)
python3 - << 'EOF'
import socket, os
d = '/tmp/claude-mcp-browser-bridge-claude'
sock = sorted(f for f in os.listdir(d) if f.endswith('.sock'))[-1]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(os.path.join(d, sock))
print('connected')
s.close()
EOF

# 3. End-to-end test with NMH message (requires Chrome with extension)
python3 - << 'EOF'
import socket, os, json, struct
d = '/tmp/claude-mcp-browser-bridge-claude'
sock = sorted(f for f in os.listdir(d) if f.endswith('.sock'))[-1]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect(os.path.join(d, sock))
msg = json.dumps({"method":"execute_tool","params":{"client_id":"test","tool":"tabs_context_mcp","args":{"createIfEmpty":True}}}).encode()
s.sendall(struct.pack('<I', len(msg)) + msg)
hdr = s.recv(4)
length = struct.unpack('<I', hdr)[0]
data = s.recv(length)
print(json.loads(data))
s.close()
EOF
```

## Debugging

- MCP logs: `~/.cache/claude-cli-nodejs/-home-claude/mcp-logs-claude-in-chrome/*.jsonl`
- `bridge_host.py` and `bridge_container.py` log to stderr
- Use `strace -f -e trace=connect,openat -p <MCP_PID>` to trace MCP server (requires `SYS_PTRACE` capability in compose)
