# 🛰️ Homelab Hub

<div align="center">

![Homelab Hub Banner](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/icons/casaos.png)

**Next-Gen All-in-One Homelab Management Dashboard, Application Launchpad & Real-Time Hardware Telemetry Hub.**

[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://github.com/gitsheikhgit/homelab-hub/pkgs/container/homelab-hub)
[![Architecture](https://img.shields.io/badge/Arch-linux%2Famd64%20%7C%20linux%2Farm64-blue)](#-setup--installation-guide)
[![Version](https://img.shields.io/badge/Release-v1.2.0-blueviolet?logo=semver&logoColor=white)](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.2.0)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Workflow](https://img.shields.io/badge/Build-Automated%20CI%2FCD-success?logo=githubactions&logoColor=white)](https://github.com/gitsheikhgit/homelab-hub/actions)
[![Built with AI](https://img.shields.io/badge/Built%20With-AI%20Pair%20Programming-8A2BE2?logo=openai&logoColor=white)](#-built-with-ai--authors-note)

*A clean, glassmorphic command center tailored for self-hosters, mini PC clusters, home server racks, and Proxmox nodes.*

[Quick Start](#-quick-start-with-docker-compose) • [Setup Guide](#-setup--installation-guide) • [Features & How-To Guides](#-features--how-to-setup-guides) • [Configuration](#%EF%B8%8F-full-configuration-reference) • [API Reference](#-api-endpoints-reference)

</div>

---

> [!NOTE]
> ### 🤖 Built with AI • Author's Note
> This entire dashboard and management platform was **built completely using AI**. 
> 
> I originally created it to solve my own homelab needs—bringing together real-time bare-metal hardware telemetry, Proxmox VE hypervisors, and dynamic Docker fleet controls into a single, unified, glassmorphic interface without running heavy enterprise monitoring stacks.
> 
> After running and perfecting it on my personal server, I wanted to open-source it and make it available for anyone in the community looking for a modern, lightweight, and self-contained server command center. Enjoy, tweak it to your heart's content, and feel free to contribute!

---

## 🌟 Why Homelab Hub?

Most server dashboards either offer a simple static bookmarks list or heavy enterprise monitoring stacks (Grafana/Prometheus) that consume gigabytes of RAM. **Homelab Hub** provides the best of both worlds:

1. **Stunning Glassmorphic Aesthetics**: Modern dark/light modes, customizable blur, custom wallpaper engine, and fluid micro-animations.
2. **Deep Bare-Metal Hardware Telemetry**: Read real CPU core temperatures, power consumption, network bandwidth, and physical drive S.M.A.R.T. health without third-party agents.
3. **Hypervisor & Fleet Control**: Monitor and manage Proxmox VE virtual machines, LXC containers, and Docker stacks in real time from a single pane of glass.
4. **Automated Maintenance & Agenda**: Track scheduled maintenance, backups, and crontab/systemd timers with an outbound RFC 5545 `.ics` calendar feed.
5. **Self-Contained & Lightweight**: Consumes under **60 MB of RAM** and starts in milliseconds. Built-in webserver and embedded zero-maintenance JSON database.

---

## 📸 Interface Showcase

<div align="center">

### 🌙 Dark Mode (Glassmorphic Midnight)
![Homelab Hub Dark Mode](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/real_homelab_dark.png?v=5)

<br>

### ⚙️ Next-Gen Modular Settings & Integrations Command Center
![Settings Modal Integrations](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/settings_modal_dark.png?v=5)

<br>

### ⚡ Native Automated Tasks & Maintenance Agenda Engine
![Settings Automated Tasks](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/settings_tasks_dark.png?v=5)

<br>

### 📊 Real-Time Silicon & Telemetry Waveforms (Beszel-Style Diagnostics)
![Telemetry Waveforms](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/telemetry_waveforms_dark.png?v=5)

<br>

### 🐳 Real-Time Docker Container Allocation Matrix
![Telemetry Containers](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/telemetry_containers_dark.png?v=5)

<br>

### ☀️ Light Mode (High-Contrast Slate)
![Homelab Hub Light Mode](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/real_homelab_light.png?v=5)

</div>

---

## 📜 Release History & Changelog

Homelab Hub adheres to [Semantic Versioning](https://semver.org/). Full version notes, commit diffs, and historical upgrades are maintained in [CHANGELOG.md](CHANGELOG.md) and tagged across all GitHub releases.

| Version | Release Date | Key Focus & Highlights | Full Notes |
| :--- | :--- | :--- | :---: |
| **v1.2.0** | 2026-09-25 | **Next-Gen Settings Command Center & Ecosystem Integrations**: Redesigned split-sidebar settings modal with instant search & filter, dedicated Integrations Hub (Portainer CE, Proxmox VE, Tailscale, LAN Host), native Automated Tasks & systemd timer engine, 1-click update checks, unified disk S.M.A.R.T. health center, and comprehensive privacy sanitization. | [Details ↗](CHANGELOG.md#v120---2026-09-25) |
| **v1.1.1** | 2026-09-24 | **1-Click Container Updates & Dynamic Ecosystem**: Robust native container recreation for standalone/compose workloads, dynamic Portainer/Docker card, conditional Tailscale, remote URL resolution, dynamic agenda tasks, and energy telemetry precision. | [Details ↗](CHANGELOG.md#v111---2026-09-24) |
| **v1.1.0** | 2026-09-20 | **Beszel-Style Silicon Waveforms & Live Telemetry Matrix**: High-resolution 1s real-time streaming graphs (CPU, RAM, Net, Disk I/O), per-core topology, live Docker container resource allocation table, full dark/light theme contrast parity. | [Details ↗](CHANGELOG.md#v110---2026-09-20) |
| **v1.0.9** | 2026-09-20 | **Mobile Viewport Overhaul & Automated History**: Zero-overflow card constraints, responsive drive arrays, automated timeline logging, universal speedtest engine. | [Details ↗](CHANGELOG.md#v109---2026-09-20) |
| **v1.0.8** | 2026-09-19 | **Proxmox Hypervisor Overhaul**: 1-click LXC/VM power controls, multi-node telemetry, Docker LAN reachability fix. | [Details ↗](CHANGELOG.md#v108---2026-09-19) |
| **v1.0.7** | 2026-09-19 | **Clean Onboarding & In-Container Docker CLI**: Zero-config container discovery on fresh installs. | [Details ↗](CHANGELOG.md#v107---2026-09-19) |
| **v1.0.0** | 2026-09-19 | **Initial Public Release**: Deep hardware telemetry, energy ledger, and app launcher. | [Details ↗](CHANGELOG.md#v100---2026-09-19) |

👉 **[Read the Full CHANGELOG.md](CHANGELOG.md)** or browse all **[GitHub Releases & Tags](https://github.com/gitsheikhgit/homelab-hub/releases)**.

---

## 🚀 Setup & Installation Guide

Homelab Hub can be deployed via **Docker Compose** (recommended), the **1-Line Quick Installer**, or as a **Native Systemd Service**.

### Method 1: Docker Compose (Recommended)

Running Homelab Hub takes **less than 60 seconds**.

#### 1. Create a Project Directory & Download `docker-compose.yml`

```bash
mkdir -p homelab-hub && cd homelab-hub
curl -fsSL https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/docker-compose.yml -o docker-compose.yml
```

Or create `docker-compose.yml` manually:

```yaml
services:
  homelab-hub:
    image: ghcr.io/gitsheikhgit/homelab-hub:latest
    container_name: homelab-hub
    restart: unless-stopped
    ports:
      - "8095:8095"

    volumes:
      # Persistent configuration, custom icons, and uploaded wallpapers
      - ./data:/app/data
      # Docker socket (enables container fleet manager & app auto-discovery)
      - /var/run/docker.sock:/var/run/docker.sock:ro
      # Host proc and sysfs (enables CPU, RAM, and thermal sensor telemetry)
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      # Block devices (enables drive S.M.A.R.T. health telemetry)
      - /dev:/dev:ro
      # Optional: Mount custom host paths to monitor disk space usage:
      # - /mnt/storage:/mnt/storage:ro
      # - /mnt/backup_hdd:/mnt/backup_hdd:ro

    # Required for raw block-level ATA/NVMe drive health queries:
    privileged: true

    environment:
      - PORT=8095
      - RUNNING_IN_DOCKER=1
      - HOST_PROC=/host/proc
      - HOST_SYS=/host/sys
      - TAILSCALE_DOMAIN=  # Optional: e.g. homelab.tailnet.ts.net
```

#### 2. Launch the Container

```bash
docker compose up -d
```

#### 3. Access the Dashboard

Open your web browser and navigate to:
```text
http://<YOUR-SERVER-IP>:8095
```

---

### Method 2: 1-Line Universal Script (`install.sh`)

For bare-metal Linux servers (Ubuntu, Debian, Fedora, Rocky, AlmaLinux, Arch) that you want to run natively via systemd:

```bash
git clone https://github.com/gitsheikhgit/homelab-hub.git
cd homelab-hub
bash install.sh
```

The script automatically:
1. Installs Python dependencies (`flask`, `psutil`, `requests`).
2. Installs system telemetry tools (`smartmontools`, `lm-sensors`, `hdparm`, `nvme-cli`).
3. Configures `/sys/class/powercap` permissions for Intel/AMD energy telemetry.
4. Creates and enables the `homelab-dashboard.service` systemd service on boot.

---

### Method 3: Native Bare-Metal / Systemd Deployment (Manual)

If you prefer to configure the systemd service manually:

```bash
# 1. Clone repository
git clone https://github.com/gitsheikhgit/homelab-hub.git /opt/homelab-hub
cd /opt/homelab-hub

# 2. Create Python virtual environment & install requirements
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Install disk diagnostic tools
sudo apt-get update && sudo apt-get install -y smartmontools lm-sensors hdparm nvme-cli

# 4. Create systemd service
sudo tee /etc/systemd/system/homelab-dashboard.service > /dev/null <<EOF
[Unit]
Description=Homelab Hub Dashboard & Server Telemetry
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/opt/homelab-hub
ExecStartPre=/usr/bin/chmod -R a+r /sys/class/powercap
ExecStart=/opt/homelab-hub/venv/bin/python3 app.py
Restart=always
RestartSec=5
Environment=PORT=8095

[Install]
WantedBy=multi-user.target
EOF

# 5. Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable --now homelab-dashboard.service
```

---

### Method 4: Standalone Docker Run

```bash
docker run -d \
  --name homelab-hub \
  --restart unless-stopped \
  -p 8095:8095 \
  -v $(pwd)/data:/app/data \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc:/host/proc:ro \
  -v /sys:/host/sys:ro \
  -v /dev:/dev:ro \
  --privileged \
  -e PORT=8095 \
  -e RUNNING_IN_DOCKER=1 \
  -e HOST_PROC=/host/proc \
  -e HOST_SYS=/host/sys \
  ghcr.io/gitsheikhgit/homelab-hub:latest
```

---

### 🛡️ Hardware Access & Security Model

Homelab Hub queries physical hardware sensors (S.M.A.R.T. registers, CPU RAPL power packages, thermal zones):

| Mode | Configuration | Security Surface |
| :--- | :--- | :--- |
| **Privileged (Simplest)** | `privileged: true` | Grants access to `/dev/sd*` and `/dev/nvme*` for ATA/SCSI passthrough. Recommended for trusted homelab environments. |
| **Granular Capabilities** | `cap_add: [SYS_RAWIO, SYS_ADMIN]` + explicit `devices:` | Limits container privileges strictly to specified disk block devices. |

To use granular capabilities instead of `privileged: true`, configure `docker-compose.yml`:
```yaml
cap_add:
  - SYS_RAWIO
  - SYS_ADMIN
devices:
  - /dev/sda:/dev/sda
  - /dev/sdb:/dev/sdb
  - /dev/nvme0n1:/dev/nvme0n1
```

---

## 🔄 Release Versioning & On-Demand Image Updates

Homelab Hub uses semantic versioning (`vMAJOR.MINOR.PATCH`) and automated multi-architecture container builds (`linux/amd64` and `linux/arm64` for Raspberry Pi / Apple Silicon).

### 🏷️ Available Docker Image Tags

| Image Tag | Behavior | Best Used For |
| :--- | :--- | :--- |
| `ghcr.io/gitsheikhgit/homelab-hub:latest` | Always tracks the newest stable release. | Most users who want new features as soon as they drop. |
| `ghcr.io/gitsheikhgit/homelab-hub:v1` | Tracks all backwards-compatible updates in the `v1.x` series. | Conservative production setups. |
| `ghcr.io/gitsheikhgit/homelab-hub:v1.2.0` | Exact immutable release build. Never changes. | Air-gapped or change-controlled environments. |

### 📥 Updating Homelab Hub

Because your configuration, custom icons, and bookmarks live in the `./data` volume mount on your host, updating Homelab Hub is **completely safe and zero-downtime**:

```bash
docker compose pull && docker compose up -d
```

*Or open the dashboard UI, click **⚙️ Settings → Updates & Releases**, and click **🔄 Check for Updates**!*

---

## 📖 Features & How-To Setup Guides

Every feature in Homelab Hub is designed to be self-configuring with intuitive web controls in the **⚙️ Settings Command Center**.

### 1. 🌐 Proxmox VE Hypervisor Integration

Homelab Hub monitors multi-node Proxmox VE clusters, virtual machines, and LXC containers directly from the top cluster strip and the **Proxmox Cluster & VMs** drawer.

#### How to Set It Up:
1. **Create an API Token in Proxmox VE**:
   - Log in to your Proxmox VE web GUI (`https://<proxmox-ip>:8006`).
   - Navigate to **Datacenter → Permissions → API Tokens**.
   - Click **Add**:
     - User: `root@pam` (or a dedicated user e.g. `homelab@pve`).
     - Token ID: `DashboardToken`.
     - Uncheck *Privilege Separation* (or grant `PVEVMAdmin` / `PVEAuditor` roles).
   - Copy the generated **Secret Token Key** (it is only shown once).
2. **Configure in Homelab Hub**:
   - In Homelab Hub, click **⚙️ Settings** in the dock or top bar.
   - Select **🔌 Integrations Hub**.
   - Under **Proxmox Virtual Environment (PVE)**:
     - Check **Enable Proxmox Integration**.
     - Enter your Proxmox host IP (e.g. `192.168.1.10`).
     - Enter Node Name (e.g. `pve`).
     - Enter Token ID (e.g. `root@pam!DashboardToken`).
     - Paste Secret Token Key.
   - Click **Save Proxmox Settings**.
3. **Multi-Node Clusters**:
   - In Settings → **System Identity** or by clicking **➕ Add Node** in the top cluster strip, add secondary hypervisors (e.g. `pve2`, TrueNAS, Unraid, Proxmox Backup Server).
4. **Using VM/LXC Power Controls**:
   - Click the **Proxmox Cluster & VMs** widget or the **VMs / PVE** dock button to open the VM Console Drawer.
   - Inspect vCPU, RAM allocation, CPU %, and guest LAN IP addresses.
   - Send 1-click **Start**, **Shutdown (ACPI)**, or **Stop** commands directly from the dashboard.

---

### 2. 🐳 Portainer CE & Docker Fleet Management

Homelab Hub provides full lifecycle management for Docker containers, live resource monitoring, 1-click container updates, and automatic application discovery.

#### How to Set It Up:
1. **Docker Socket Passthrough**:
   - Ensure `/var/run/docker.sock:/var/run/docker.sock:ro` is mounted in your `docker-compose.yml`.
   - Homelab Hub auto-detects the Docker daemon instantly on startup.
2. **Portainer Web UI Integration**:
   - In Settings → **🔌 Integrations Hub**, enter your Portainer Web UI URL (e.g. `http://192.168.1.100:9000`).
   - Click **Test Docker Socket** to verify connectivity.
3. **Auto-Detect Applications**:
   - Click **⚡ Auto-Detect** on the **Services & Applications** card header.
   - Homelab Hub probes all active containers and published port bindings, matches them against a built-in library of 100+ homelab services, and generates proposed launchpad cards.
   - Click **Import All** to add them to your dashboard in seconds.
4. **1-Click In-Place Container Updates**:
   - When a container has an update available in its remote registry, a **🚀 Update Available** badge appears.
   - Click **Update Container**. Homelab Hub pulls the latest image tag, stops the old container, recreates the container in-place—**preserving all volume mounts, environment variables, published ports, restart policies, and network attachments**—and starts the new container with automatic rollback protection.
5. **Self-Healing & Docker Pruning**:
   - Unhealthy or stopped containers can be restarted with 1-click from the **Docker Fleet** card.
   - Click **Prune System** to safely remove dangling image layers, stopped builder containers, and unused build cache (`docker system prune -f`).

---

### 3. 📊 Beszel-Style Silicon Waveforms & Real-Time Telemetry

Experience fluid 60 FPS real-time performance graphs for host CPU, Memory, Network bandwidth, and Disk I/O without running Prometheus or heavy time-series databases.

#### How to Set It Up:
1. **Host Mounts**:
   - Mount `/proc:/host/proc:ro` and `/sys:/host/sys:ro` in your `docker-compose.yml`.
2. **Thermal Sensors & Hardware Topology**:
   - Homelab Hub automatically detects thermal hardware paths (`/sys/class/thermal/` and `/sys/class/hwmon/`), with native support for AMD `k10temp`, Intel `coretemp`, and ARM SOC sensors.
   - Machine model names (e.g. *Lenovo ThinkCentre*, *Dell OptiPlex*, *HP EliteDesk*) are read via DMI/SMBIOS.
3. **Real-Time Streaming Diagnostics**:
   - The central **Live Telemetry Waveforms** card streams 1-second interval hardware deltas.
   - Click **Inspect ↗** to open the full-screen diagnostics modal:
     - **Waveforms & Trends**: Continuous SVG timeline with time-window presets (**1m**, **2m**, **5m**, **10m**) and interactive crosshair hover scrubbing.
     - **CPU & Cores Topology**: Per-core frequency and load utilization.
     - **Memory & Swap Pools**: Active RAM, cached/buffers, and swap breakdown.
     - **Network & Disk I/O**: Real-time throughput rates and lifetime written/read gigabytes.
     - **Containers Matrix**: Live per-container CPU percentage and memory allocation table with instant text filtering and column sorting.

---

### 4. 💾 Storage Pools, Monitored Drives & S.M.A.R.T. Health

Monitor physical NVMe SSDs, SATA drives, ZFS pools, and filesystem mounts with predictive drive failure warnings and an integrated SSD garbage collector.

#### How to Set It Up:
1. **Drive Block Access**:
   - In `docker-compose.yml`, set `privileged: true` and mount `/dev:/dev:ro`.
2. **Auto-Detecting Disks & Mounts**:
   - In Settings → **Storage & Disks** (or on the dashboard **Storage Pools & Drives** card), click **➕ Add Drive** or **⚡ Auto-Detect Mounts**.
   - Homelab Hub scans `/proc/mounts`, `lsblk`, and `/dev/disk/by-id/` to display your storage topology.
3. **Running S.M.A.R.T. Health Diagnostics**:
   - Click **Run S.M.A.R.T. Diagnostic**.
   - Homelab Hub queries raw drive registers using `smartctl` and reports:
     - Drive Temperature & Lifetime Power-On Hours
     - Reallocated / Bad Sector Counts
     - Lifetime Terabytes Written (TBW) and Wear Level %
4. **SSD Garbage Collector**:
   - Click **🧹 Clean SSD** on the Storage card.
   - The garbage collector inspects your system for safe disk recovery opportunities:
     - Docker builder cache and dangling image layers
     - Old systemd journal log archives (`journalctl --vacuum-time=7d`)
     - Linux apt/dnf package cache archives
     - Temporary files in `/tmp`
   - Click **Clean Selected Items** to instantly reclaim gigabytes of disk space.

---

### 5. ⚡ Native Automated Tasks & Maintenance Agenda

Keep your homelab running smoothly by tracking cron jobs, systemd timers, snapshot schedules, and backups with automated calendar integration.

#### How to Set It Up:
1. **Adding Custom Maintenance Tasks**:
   - Open **⚙️ Settings → ⚡ Automated Tasks**.
   - Click **➕ Add Task**.
   - Enter Task Name (e.g. *Nightly Borg Backup*, *Docker Fleet Prune*, *ZFS Scrub*).
   - Select Schedule (**Daily**, **Weekly**, **Monthly**, or Custom Cron).
   - Assign a Category tag (**Backup**, **Maintenance**, **Security**, **System**).
   - Click **Save Task**.
2. **Auto-Detecting Host Systemd Timers**:
   - Click **⚡ Auto-Detect Timers**.
   - Homelab Hub queries host timers (`systemctl list-timers`) and imports scheduled system automation (e.g. `fstrim.timer`, `apt-daily.timer`, `logrotate.timer`) directly into your agenda.
3. **Subscribing via iCalendar (`.ics`) Feed**:
   - Subscribe to your homelab maintenance schedule in **Apple Calendar**, **Google Calendar**, or **Outlook**:
     ```text
     http://<YOUR-SERVER-IP>:8095/api/calendar/feed.ics
     ```
   - All scheduled tasks and maintenance windows sync automatically to your phone and desktop.

---

### 6. 🚀 Quick Apps Launchpad & Dual Network Resolution

Organize your homelab web services with categorized workspaces, drag-and-drop reordering, and seamless switching between local LAN and remote Tailscale access.

#### How to Set It Up:
1. **Adding & Customizing Cards**:
   - Click **➕ Add App** in the header or **➕ Add Card Manually** in the services grid.
   - Fill in:
     - **Service Name** (e.g. *Immich Photos*, *Nextcloud*, *Home Assistant*).
     - **Subtitle** (e.g. *Self-Hosted Photo & Video Vault*).
     - **Local LAN URL** (e.g. `http://192.168.1.100:2283`).
     - **Tailscale Remote URL** (e.g. `http://homelab.tailnet.ts.net:2283`).
     - **Category** (*Media*, *Cloud & Office*, *System*, *Smart Home*).
     - **Icon**: Choose from 40+ built-in high-resolution icons or upload a custom image.
2. **Adding Secondary Action Links**:
   - Many services feature both a user-facing player and an administrative backend (e.g. Navidrome Web Player + Librarian Admin, Nextcloud Web + AIO Admin).
   - Configure **Second Link Name** and **Second LAN / Tailscale URL** to display an action button directly on the card.
3. **1-Click LAN / Tailscale Mode Switcher**:
   - Click the **🏠 LAN Local / 🔒 Tailscale Remote** toggle in the dashboard header.
   - Every application card, dock icon, and container link across the entire dashboard instantly switches its target URL.
4. **Drag-and-Drop Organization**:
   - Click and drag the **⠿** handle on any card to reposition it. Layout and ordering persist automatically in `data/cards.json`.

---

### 7. 🛡️ Disaster Recovery, Backup Kit & Emergency Passport

Never lose your homelab configuration. Homelab Hub includes complete backup/restore tooling and an offline emergency runbook generator.

#### How to Set It Up:
1. **Exporting Full Backups**:
   - Open **⚙️ Settings → 💾 Backup & Migration**.
   - Click **Export Full Backup Package**.
   - Homelab Hub packages all card bookmarks, dashboard settings, node configurations, custom uploaded wallpapers, and task schedules into an archive (`homelab-backup.json`).
2. **Restoring from Backup**:
   - On a fresh installation, open Settings → Backup & Migration.
   - Upload your backup file and click **Inspect & Restore**.
   - Your entire dashboard environment is restored in seconds.
3. **The Offline Emergency Passport**:
   - Navigate to `http://<YOUR-SERVER-IP>:8095/passport` in your browser.
   - Homelab Hub compiles an offline, self-contained HTML runbook containing:
     - Host hardware specs, MAC addresses, and network interface configurations
     - Hypervisor node IPs and API endpoints
     - Complete Docker container fleet mapping with port bindings and volume paths
     - Disaster recovery emergency terminal commands
   - Save or print this document to keep an air-gapped recovery runbook in case of network or power failure.

---

### 8. 🎨 Appearance, Themes & Custom Wallpapers

Customize the look and feel of your command center to match your setup.

#### How to Set It Up:
1. **Theme Selection**:
   - In Settings → **🎨 Appearance & Dock**, choose between:
     - 🌙 **Dark Mode**: Sleek midnight glassmorphic aesthetic.
     - ☀️ **Light Mode**: High-contrast slate theme with WCAG AAA readability.
     - 💻 **System Theme**: Automatically matches your OS light/dark preference.
2. **Wallpaper Engine**:
   - Upload any custom background image (JPG, PNG, WebP) directly through the settings modal.
   - Adjust **Backdrop Blur** slider (0px to 20px) and **Background Brightness** slider (0% to 100%) for optimal text legibility.
3. **Dock Position**:
   - Choose between **Bottom Floating Dock** or **Hidden Dock** for maximum screen space.
4. **Omni Web Search Bar**:
   - Search the web directly from your dashboard. Choose your preferred search provider: **Brave**, **Google**, **DuckDuckGo**, or **Bing**.

---

## ⚙️ Full Configuration Reference

### Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `PORT` | `8095` | Port the dashboard webserver binds to inside the container. |
| `RUNNING_IN_DOCKER` | `1` | Informs the Python app to execute `smartctl` directly as root without `sudo`. |
| `HOST_PROC` | `/host/proc` | Host `/proc` filesystem mount for reading host CPU load and RAM. |
| `HOST_SYS` | `/host/sys` | Host `/sys` filesystem mount for reading thermal sensors and DMI data. |
| `TAILSCALE_DOMAIN` | `""` | Optional MagicDNS domain name for automatic remote link generation (e.g. `homelab.tailnet.ts.net`). |
| `PROXMOX_TOKENS` | `""` | Optional JSON array for Proxmox API tokens via environment variable. |

---

### `data/settings.json` Configuration Reference

All dashboard configurations are stored in `data/settings.json`. If this file does not exist, Homelab Hub automatically creates it using [`data/settings.json.example`](file:///home/cloud/server-dashboard/data/settings.json.example):

```json
{
  "theme": "dark",
  "server_name": "Homelab Hub",
  "lan_host": "192.168.1.100",
  "tailscale_domain": "homelab.tailnet.ts.net",
  "elec_rate_kwh": 0.23,
  "monitored_drives": [
    {
      "id": "drive_root",
      "name": "System Root NVMe SSD",
      "mount": "/",
      "dev": "/dev/nvme0n1"
    }
  ],
  "proxmox_tokens": [
    {
      "host": "192.168.1.10",
      "node_id": "pve",
      "nodename": "pve",
      "token": "root@pam!DashboardToken",
      "secret": "your-api-secret-token"
    }
  ]
}
```

---

### Reverse Proxy Examples

<details>
<summary><b>Nginx Proxy Manager / Nginx</b></summary>

```nginx
server {
    listen 80;
    server_name hub.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8095;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
</details>

<details>
<summary><b>Caddy</b></summary>

```caddy
hub.yourdomain.com {
    reverse_proxy 127.0.0.1:8095
}
```
</details>

<details>
<summary><b>Traefik (Docker Labels)</b></summary>

```yaml
services:
  homelab-hub:
    image: ghcr.io/gitsheikhgit/homelab-hub:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.homelab.rule=Host(`hub.yourdomain.com`)"
      - "traefik.http.routers.homelab.entrypoints=websecure"
      - "traefik.http.routers.homelab.tls.certresolver=myresolver"
      - "traefik.http.services.homelab.loadbalancer.server.port=8095"
```
</details>

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/stats` | Full hardware telemetry (CPU, RAM, temp, network, drives, containers, Proxmox). |
| `GET` | `/api/telemetry/history` | High-resolution 1-second streaming telemetry buffer for Beszel waveforms. |
| `GET` | `/api/system/version` | Current running application version and Docker image details. |
| `GET` | `/api/system/update-check` | Query GitHub Container Registry for available image updates. |
| `POST`| `/api/system/pull-image` | Trigger on-demand Docker pull stream from the dashboard UI. |
| `GET` | `/api/tasks` | Retrieve all scheduled maintenance tasks and systemd timers. |
| `POST`| `/api/tasks` | Create a new maintenance task. |
| `DELETE`| `/api/tasks/<id>` | Delete an automated task. |
| `POST`| `/api/tasks/auto-detect` | Auto-detect host systemd timers and crontabs. |
| `GET` | `/api/cards` | Retrieve all custom application launchpad cards. |
| `POST`| `/api/cards` | Create a new application card. |
| `PUT` | `/api/cards/<id>` | Update an existing application card. |
| `DELETE`| `/api/cards/<id>` | Delete an application card. |
| `GET` | `/api/cards/auto-detect` | Scan local Docker daemon and propose new application cards. |
| `POST`| `/api/cards/auto-create` | Batch import proposed Docker application cards. |
| `GET` | `/api/settings` | Retrieve user dashboard appearance, layout, and widget configuration. |
| `POST`| `/api/settings` | Save modified dashboard settings. |
| `GET` | `/api/drives/detect` | Probe system mounts and suggest drives for S.M.A.R.T. monitoring. |
| `POST`| `/api/drives/config` | Update monitored disk and mount configuration. |
| `POST`| `/api/run-smart-diagnostic`| Trigger an immediate S.M.A.R.T. diagnostic check across all drives. |
| `GET` | `/api/system/ssd-garbage/scan`| Scan primary disk for recoverable Docker/journal/apt space. |
| `POST`| `/api/system/ssd-garbage/clean`| Execute disk space reclamation for selected components. |
| `POST`| `/api/docker/power` | Control Docker container state (`action`: `start` / `stop` / `restart`). |
| `POST`| `/api/docker/update-container`| Perform 1-click in-place container recreation with the latest image. |
| `POST`| `/api/docker/prune` | Execute Docker system cache prune. |
| `POST`| `/api/proxmox/vm/power` | Send VM/LXC power commands (`action`: `start` / `stop` / `shutdown`). |
| `GET` | `/api/calendar/feed.ics` | Live RFC 5545 iCalendar feed subscription. |
| `GET` | `/api/weather` | Current weather and forecast for configured coordinates. |

---

## 🛡️ Security & Privacy

- **Zero External Trackers**: No third-party tracking scripts, cloud phone-home beacons, or external analytics.
- **Local Credential Storage**: All API tokens and passwords remain strictly on your server in `data/settings.json`.
- **Git Protection**: The provided `.gitignore` automatically prevents personal credentials, local IPs, and diagnostic caches from being committed.
- **Built-In Demo Mode (`?demo=1`)**: Automatically sanitizes hostnames, IPs, and domains when taking screenshots or sharing screen captures.

---

## 🤝 Contributing

Contributions, feature suggestions, and pull requests are welcome!

1. Fork the repository on GitHub.
2. Create a feature branch: `git checkout -b feature/amazing-feature`.
3. Commit your changes: `git commit -m 'Add amazing feature'`.
4. Push to the branch: `git push origin feature/amazing-feature`.
5. Open a Pull Request.

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

<div align="center">
  <sub>Built with ❤️ for the self-hosted and homelab community.</sub>
</div>
