#!/usr/bin/env bash
# start_inspector.sh — Launch MCP Inspector against this server.
# Usage: ./start_inspector.sh
#
# NOTE: The path to this project contains spaces ("Code Base"), which causes
# the MCP Inspector's argument parser to split the path incorrectly.
# To work around this, we create a temporary wrapper script in /tmp (no spaces).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$(dirname "$SCRIPT_DIR")/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "[error] venv not found at $VENV_PYTHON"
  echo "Run: python3 -m venv .venv && .venv/bin/pip install fastmcp"
  exit 1
fi

# Init DB if needed
if [ ! -f "$SCRIPT_DIR/lab.db" ]; then
  echo "[init] Creating database..."
  "$VENV_PYTHON" "$SCRIPT_DIR/init_db.py"
fi

# Create a wrapper script in /tmp to avoid path-with-spaces issue
WRAPPER="/tmp/mcp_lab26_server.sh"
cat > "$WRAPPER" << WRAPPER_EOF
#!/usr/bin/env bash
exec "$VENV_PYTHON" "$SCRIPT_DIR/mcp_server.py" "\$@"
WRAPPER_EOF
chmod +x "$WRAPPER"

echo "[inspector] Starting MCP Inspector..."
echo "[inspector] Wrapper: $WRAPPER"
echo ""
echo "Open the Inspector URL shown below in your browser."
echo ""

mkdir -p "$SCRIPT_DIR/.npm-cache"
NPM_CONFIG_CACHE="$SCRIPT_DIR/.npm-cache" \
  npx -y @modelcontextprotocol/inspector "$WRAPPER"
