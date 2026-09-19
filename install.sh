#!/bin/bash
set -euo pipefail

DEST_DIR="${HOME}/.config/omarchy/plugins/fleet.health"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing Omarchy Fleet Plugin to ${DEST_DIR}..."
mkdir -p "${DEST_DIR}/bin" "${HOME}/.local/bin"
cp "${SCRIPT_DIR}/manifest.json" "${DEST_DIR}/"
cp "${SCRIPT_DIR}/Panel.qml" "${DEST_DIR}/"
cp "${SCRIPT_DIR}/README.md" "${DEST_DIR}/"
cp "${SCRIPT_DIR}/LICENSE" "${DEST_DIR}/"
cp "${SCRIPT_DIR}/uninstall.sh" "${DEST_DIR}/"
cp "${SCRIPT_DIR}/bin/omarchy-fleet-status" "${DEST_DIR}/bin/"
cp "${SCRIPT_DIR}/bin/omarchy-fleet-health-report" "${DEST_DIR}/bin/"
chmod +x "${DEST_DIR}/uninstall.sh" "${DEST_DIR}/bin/omarchy-fleet-status" "${DEST_DIR}/bin/omarchy-fleet-health-report"

cp "${SCRIPT_DIR}/bin/omarchy-fleet-status" "${HOME}/.local/bin/"
cp "${SCRIPT_DIR}/bin/omarchy-fleet-health-report" "${HOME}/.local/bin/"
chmod +x "${HOME}/.local/bin/omarchy-fleet-status" "${HOME}/.local/bin/omarchy-fleet-health-report"

echo "Fleet plugin installed successfully!"
echo "To add it to your Omarchy bar, add 'fleet.health' to your bar widgets in ~/.config/omarchy/shell.json"
