#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Homelab Dashboard — Installation Script
# Run as your regular user (NOT root). Script will sudo when needed.
# Usage:  bash install.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="homelab-dashboard"
SERVICE_USER="$(whoami)"
PYTHON_BIN="$(which python3)"
PORT=8095

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'
BLU='\033[0;34m'; CYN='\033[0;36m'; RST='\033[0m'; BLD='\033[1m'

info()  { echo -e "${BLU}[INFO]${RST}  $*"; }
ok()    { echo -e "${GRN}[OK]${RST}    $*"; }
warn()  { echo -e "${YEL}[WARN]${RST}  $*"; }
die()   { echo -e "${RED}[ERR]${RST}   $*"; exit 1; }
step()  { echo -e "\n${BLD}${CYN}── $* ──${RST}"; }

# ── 1. Check prerequisites ────────────────────────────────────────────────────
step "Checking prerequisites"

[[ $(id -u) -eq 0 ]] && die "Do NOT run as root. Run as your regular user."
command -v python3  &>/dev/null || die "python3 not found. Install it first."
command -v pip3     &>/dev/null || warn "pip3 not found — trying pip."
command -v systemctl &>/dev/null || die "systemd not found. This script is for systemd-based distros."

ok "User: ${SERVICE_USER} | Python: ${PYTHON_BIN}"

# ── 2. Install Python dependencies ────────────────────────────────────────────
step "Installing Python dependencies"

cd "${SCRIPT_DIR}"
if [[ -f requirements.txt ]]; then
    pip3 install -r requirements.txt --quiet && ok "Python packages installed."
else
    warn "requirements.txt not found — installing common packages."
    pip3 install flask psutil requests --quiet && ok "Core packages installed."
fi

# ── 3. Install system tools (smartmontools, lm-sensors) ──────────────────────
step "Installing system monitoring tools"

# Detect package manager
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y smartmontools lm-sensors hdparm nvme-cli &>/dev/null && \
        ok "smartmontools + lm-sensors installed."
elif command -v dnf &>/dev/null; then
    sudo dnf install -y smartmontools lm_sensors hdparm nvme-cli &>/dev/null && \
        ok "smartmontools + lm_sensors installed."
elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm smartmontools lm_sensors hdparm nvme-cli &>/dev/null && \
        ok "smartmontools + lm_sensors installed."
else
    warn "Unknown package manager — please install: smartmontools lm-sensors hdparm nvme-cli manually."
fi

# ── 4. Configure sudo for SMART / drive stats ─────────────────────────────────
step "Configuring sudo access for hardware telemetry"

SUDOERS_FILE="/etc/sudoers.d/${SERVICE_NAME}"

# Minimal sudoers: only the exact binaries the dashboard needs
SUDOERS_CONTENT="${SERVICE_USER} ALL=(ALL) NOPASSWD: \
/usr/sbin/smartctl, \
/usr/bin/smartctl, \
/sbin/smartctl, \
/usr/sbin/hdparm, \
/usr/bin/hdparm, \
/usr/sbin/nvme, \
/usr/bin/nvme, \
/usr/bin/sensors, \
/usr/sbin/sensors"

# If the user already has NOPASSWD:ALL (full sudo, e.g. admin workstation),
# we skip the minimal file — it's already covered.
if sudo -n true 2>/dev/null && sudo grep -q "NOPASSWD: ALL" /etc/sudoers /etc/sudoers.d/* 2>/dev/null; then
    ok "Full NOPASSWD sudo already configured — no additional sudoers needed."
else
    # Write minimal sudoers file with visudo validation
    echo "${SUDOERS_CONTENT}" | sudo tee "${SUDOERS_FILE}" > /dev/null
    sudo chmod 440 "${SUDOERS_FILE}"

    # Validate with visudo — if it fails, remove and warn
    if sudo visudo -cf "${SUDOERS_FILE}" &>/dev/null; then
        ok "Sudoers rule written: ${SUDOERS_FILE}"
        echo -e "  ${YEL}Grants passwordless access to:${RST} smartctl, hdparm, nvme, sensors"
    else
        sudo rm -f "${SUDOERS_FILE}"
        die "visudo validation failed! Sudoers NOT written. Please add manually:\n${SUDOERS_CONTENT}"
    fi
fi

# ── 5. Create data directory and default settings ──────────────────────────────
step "Setting up data directory"

mkdir -p "${SCRIPT_DIR}/data"
SETTINGS_FILE="${SCRIPT_DIR}/data/settings.json"

if [[ ! -f "${SETTINGS_FILE}" ]]; then
    if [[ -f "${SCRIPT_DIR}/data/settings.json.example" ]]; then
        cp "${SCRIPT_DIR}/data/settings.json.example" "${SETTINGS_FILE}"
        ok "Default settings.json created from template."
    fi
else
    ok "Existing settings.json preserved."
fi

CARDS_FILE="${SCRIPT_DIR}/data/cards.json"
if [[ ! -f "${CARDS_FILE}" ]]; then
    ok "Fresh system: cards will be dynamically detected from this host's Docker containers on first launch."
fi

# ── 6. Create / update systemd service ────────────────────────────────────────
step "Installing systemd service"

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Homelab Dashboard (Flask)
After=network.target docker.service
Wants=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_BIN} ${SCRIPT_DIR}/app.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"

sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    ok "Service ${SERVICE_NAME} is running!"
else
    warn "Service may not have started. Check: journalctl -u ${SERVICE_NAME} -n 30"
fi

# ── 7. Auto-detect drives and write to settings ────────────────────────────────
step "Auto-detecting storage drives"

sleep 2  # give Flask a moment to fully start

DETECT_RESPONSE=$(curl -s --max-time 10 "http://localhost:${PORT}/api/drives/detect" 2>/dev/null || echo "{}")
DRIVE_COUNT=$(echo "${DETECT_RESPONSE}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('drives',[])))" 2>/dev/null || echo 0)

if [[ "${DRIVE_COUNT}" -gt 0 ]]; then
    ok "Detected ${DRIVE_COUNT} storage drives. Opening settings to configure..."
    # Save detected drives automatically
    curl -s -X POST "http://localhost:${PORT}/api/drives/config" \
         -H "Content-Type: application/json" \
         -d "${DETECT_RESPONSE}" > /dev/null 2>&1 || true
else
    warn "No drives auto-detected. You can add them manually in Dashboard Settings → Widgets → Storage."
fi

# ── 8. Done ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GRN}${BLD}╔══════════════════════════════════════════════════════════╗${RST}"
echo -e "${GRN}${BLD}║  ✅  Homelab Dashboard installation complete!             ║${RST}"
echo -e "${GRN}${BLD}╚══════════════════════════════════════════════════════════╝${RST}"
echo ""
echo -e "  ${BLD}Dashboard URL:${RST}  ${CYN}http://$(hostname -I | awk '{print $1}'):${PORT}/${RST}"
echo -e "  ${BLD}Service:${RST}        ${CYN}systemctl status ${SERVICE_NAME}${RST}"
echo -e "  ${BLD}Logs:${RST}           ${CYN}journalctl -u ${SERVICE_NAME} -f${RST}"
echo ""
echo -e "  ${YEL}💡 Sudo note:${RST}"
echo -e "  The dashboard uses ${BLD}sudo -n smartctl${RST} to read real hardware"
echo -e "  temperatures and SMART health without passwords. The sudoers"
echo -e "  rule written to ${BLD}${SUDOERS_FILE}${RST} grants ONLY the"
echo -e "  specific binaries needed (smartctl, hdparm, nvme, sensors)."
echo -e "  No shell, no package manager, no full root — minimal attack surface."
echo ""
