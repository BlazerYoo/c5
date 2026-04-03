#!/bin/bash
set -e

if [ -n "$CLAUDE_CREDENTIALS" ]; then
    mkdir -p ~/.claude
    echo "$CLAUDE_CREDENTIALS" > ~/.claude/.credentials.json
fi

# Install fake chrome-native-host (expected by Claude Code, not used by MCP)
mkdir -p ~/.claude/chrome
cat > ~/.claude/chrome/chrome-native-host << 'EOF'
#!/bin/bash
exec python3 /home/claude/chrome_native_host.py
EOF
chmod +x ~/.claude/chrome/chrome-native-host

# Start Python bridge: Unix socket -> TCP to host bridge
# bridge_container.py calls os.setsid() internally to detach from the terminal
# process group (protects it from Ctrl+C), mirroring the original `setsid socat ...`.
SOCK_DIR="/tmp/claude-mcp-browser-bridge-${USER}"
mkdir -p -m 700 "$SOCK_DIR"
SOCK_PATH="${SOCK_DIR}/$$.sock"

BRIDGE_SOCK_PATH="$SOCK_PATH" python3 /home/claude/bridge_container.py &

exec "$@"
