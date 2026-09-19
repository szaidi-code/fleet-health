#!/bin/bash
# Uninstall the fleet.health Omarchy plugin and clean up installed scripts.

set -euo pipefail

DEST_DIR="${HOME}/.config/omarchy/plugins/fleet.health"
BIN_DIR="${PREFIX:-$HOME/.local/bin}"

echo "Uninstalling fleet.health plugin..."

# Remove installed plugin directory
if [[ -d "$DEST_DIR" ]]; then
  rm -rf "$DEST_DIR"
  echo "Removed ${DEST_DIR}"
fi

# Remove installed binaries
for bin in omarchy-fleet-status omarchy-fleet-health-report omarchy-fleet-health-report.real; do
  if [[ -f "${BIN_DIR}/${bin}" ]]; then
    rm -f "${BIN_DIR}/${bin}"
    echo "Removed ${BIN_DIR}/${bin}"
  fi
done

echo "fleet.health has been uninstalled."
echo "Remember to remove 'fleet.health' from your bar layout in ~/.config/omarchy/shell.json if configured."
