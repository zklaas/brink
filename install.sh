#!/usr/bin/env bash
# Install a `brink` launcher on your PATH (~/.local/bin by default).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${1:-$HOME/.local/bin}"
LAUNCHER="$BIN_DIR/brink"

mkdir -p "$BIN_DIR"
cat > "$LAUNCHER" <<EOT
#!/usr/bin/env bash
exec python3 "$APP_DIR/brink_app.py" "\$@"
EOT
chmod +x "$LAUNCHER"

echo "Installed: $LAUNCHER"

# Register a dash / "Show Applications" entry with the Brink icon (best effort).
if [ -x "$APP_DIR/install-desktop.sh" ]; then
  "$APP_DIR/install-desktop.sh" "$BIN_DIR" || true
fi

python3 -c "import PyQt6.QtWidgets" 2>/dev/null || \
  echo "NOTE: Brink needs PyQt6:  sudo apt install python3-pyqt6"

if ! printf '%s' ":$PATH:" | grep -q ":$BIN_DIR:"; then
  echo "NOTE: $BIN_DIR is not on your PATH."
  echo "  Add this line to ~/.bashrc then restart your shell:"
  echo "    export PATH=\"$BIN_DIR:\$PATH\""
else
  echo "Run it with:  brink"
fi
