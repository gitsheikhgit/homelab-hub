# 🛰️ Homelab Hub

<div align="center">

![Homelab Hub Banner](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/icons/casaos.png)

**Next-Gen All-in-One Homelab Management Dashboard, Application Launchpad & Real-Time Hardware Telemetry Hub.**

[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://github.com/gitsheikhgit/homelab-hub/pkgs/container/homelab-hub)
[![Architecture](https://img.shields.io/badge/Arch-linux%2Famd64%20%7C%20linux%2Farm64-blue)](#-docker-deployment-recommended)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![GitHub Workflow](https://img.shields.io/badge/Build-Automated%20CI%2FCD-success?logo=githubactions&logoColor=white)](https://github.com/gitsheikhgit/homelab-hub/actions)

[![Built with AI](https://img.shields.io/badge/Built%20With-AI%20Pair%20Programming-8A2BE2?logo=openai&logoColor=white)](#-built-with-ai--authors-note)

*A clean, glassmorphic command center tailored for self-hosters, mini PC clusters, home server racks, and Proxmox nodes.*

[Docker Install Guide](#-installing-docker-on-a-new-system) • [Quick Start](#-quick-start-with-docker-compose) • [Features Walkthrough](#-detailed-features--functions-guide) • [Configuration](#%EF%B8%8F-full-configuration-reference) • [API Reference](#-api-endpoints-reference)

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

Most server dashboards either offer a simple bookmarks list or heavy enterprise monitoring stacks (Grafana/Prometheus) that consume gigabytes of RAM. **Homelab Hub** provides the best of both worlds:

1. **Stunning Glassmorphic Aesthetics**: Modern dark/light modes, customizable blur, custom wallpaper engine, and fluid micro-animations.
2. **Deep Bare-Metal Hardware Telemetry**: Read real CPU core temperatures, power consumption, network bandwidth, and physical drive S.M.A.R.T. health without third-party agents.
3. **Hypervisor & Fleet Control**: Monitor and manage Proxmox VE virtual machines, LXC containers, and Docker stacks in real time from a single pane of glass.
4. **Self-Contained & Lightweight**: Consumes under **60 MB of RAM** and starts in milliseconds. Built-in webserver and embedded zero-maintenance JSON database.

---

## 📸 Interface Showcase

<div align="center">

### 📊 Real-Time Silicon & Telemetry Waveforms (Beszel-Style Diagnostics)
![Telemetry Waveforms](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/telemetry_waveforms_dark.png?v=4)

<br>

### 🐳 Real-Time Docker Container Allocation Matrix
![Telemetry Containers](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/telemetry_containers_dark.png?v=4)

<br>

### 🌙 Dark Mode (Glassmorphic Midnight)
![Homelab Hub Dark Mode](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/real_homelab_dark.png?v=4)

<br>

### ☀️ Light Mode (High-Contrast Slate)
![Homelab Hub Light Mode](https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/static/screenshots/real_homelab_light.png?v=4)

</div>

---

## 📜 Release History & Changelog

Homelab Hub adheres to [Semantic Versioning](https://semver.org/). Full version notes, commit diffs, and historical upgrades are maintained in [CHANGELOG.md](CHANGELOG.md) and tagged across all GitHub releases.

| Version | Release Date | Key Focus & Highlights | Full Notes |
| :--- | :--- | :--- | :---: |
| **v1.1.1** | 2026-09-24 | **1-Click Container Updates & Dynamic Ecosystem**: Robust native container recreation for standalone/compose workloads, dynamic Portainer/Docker card, conditional Tailscale, remote URL resolution, dynamic agenda tasks, and energy telemetry precision. | [Details ↗](CHANGELOG.md#v111---2026-09-24) |
| **v1.1.0** | 2026-09-20 | **Beszel-Style Silicon Waveforms & Live Telemetry Matrix**: High-resolution 1s real-time streaming graphs (CPU, RAM, Net, Disk I/O), per-core topology, live Docker container resource allocation table, full dark/light theme contrast parity. | [Details ↗](CHANGELOG.md#v110---2026-09-20) |
| **v1.0.9** | 2026-09-20 | **Mobile Viewport Overhaul & Automated History**: Zero-overflow card constraints, responsive drive arrays, automated timeline logging, universal speedtest engine. | [Details ↗](CHANGELOG.md#v109---2026-09-20) |
| **v1.0.8** | 2026-09-19 | **Proxmox Hypervisor Overhaul**: 1-click LXC/VM power controls, multi-node telemetry, Docker LAN reachability fix. | [Details ↗](CHANGELOG.md#v108---2026-09-19) |
| **v1.0.7** | 2026-09-19 | **Clean Onboarding & In-Container Docker CLI**: Zero-config container discovery on fresh installs. | [Details ↗](CHANGELOG.md#v107---2026-09-19) |
| **v1.0.0** | 2026-09-19 | **Initial Public Release**: Deep hardware telemetry, energy ledger, and app launcher. | [Details ↗](CHANGELOG.md#v100---2026-09-19) |

👉 **[Read the Full CHANGELOG.md](CHANGELOG.md)** or browse all **[GitHub Releases & Tags](https://github.com/gitsheikhgit/homelab-hub/releases)**.

---

## 🛠️ Installing Docker on a New System

If you are setting up Homelab Hub on a brand new or freshly installed Linux server, follow this quick guide to install Docker and Docker Compose.

### Method 1: The Fast 1-Line Universal Script (Recommended)

Docker provides an official convenience script that automatically configures repositories and installs the latest Docker Engine and Docker Compose plugin on Ubuntu, Debian, Rocky, AlmaLinux, CentOS, and Raspberry Pi OS:

```bash
# 1. Download and run official Docker convenience script
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. Add your current user to the 'docker' group (avoids needing sudo for docker commands)
sudo usermod -aG docker $USER

# 3. Enable and start Docker service on boot
sudo systemctl enable --now docker

# 4. Refresh your shell group permissions
newgrp docker
```

---

### Method 2: Distribution-Specific Package Installation

<details>
<summary><b>Click to expand distribution-specific guides (Ubuntu, Debian, RHEL, Arch)</b></summary>

#### Ubuntu (22.04 / 24.04 LTS) & Debian (11 / 12)
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
sudo systemctl enable --now docker
```

#### Rocky Linux / AlmaLinux / RHEL / CentOS Stream 9
```bash
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
sudo systemctl enable --now docker
```

#### Fedora
```bash
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
sudo systemctl enable --now docker
```

#### Arch Linux
```bash
sudo pacman -Syu --noconfirm docker docker-compose
sudo usermod -aG docker $USER
sudo systemctl enable --now docker
```
</details>

---

### Verifying Docker Installation

Verify that Docker and the Docker Compose plugin are working:

```bash
docker --version
docker compose version
```

You should see output similar to:
```text
Docker version 27.x.x, build ...
Docker Compose version v2.x.x
```

---

## 🚀 Quick Start with Docker Compose

Once Docker is installed, running Homelab Hub takes **less than 60 seconds**.

### 1. Download or Create `docker-compose.yml`

Create a project directory and create `docker-compose.yml`:

```bash
mkdir -p homelab-hub && cd homelab-hub
curl -fsSL https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/docker-compose.yml -o docker-compose.yml
```

Or paste this file directly:

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
      - TAILSCALE_DOMAIN=  # Optional: e.g. my-server.ts.net
```

### 2. Launch the Hub

```bash
docker compose up -d
```

### 3. Open the Dashboard

Open your web browser and navigate to:
```text
http://<YOUR-SERVER-IP>:8095
```

---

## 🔄 Release Versioning & On-Demand Image Updates

Homelab Hub uses semantic versioning (`vMAJOR.MINOR.PATCH`) and automated multi-architecture container builds (`linux/amd64` and `linux/arm64` for Raspberry Pi / Apple Silicon).

### 🏷️ Available Docker Image Tags

In your `docker-compose.yml`, you can choose the tag that fits your update strategy:

| Image Tag | Behavior | Best Used For |
| :--- | :--- | :--- |
| `ghcr.io/gitsheikhgit/homelab-hub:latest` | Always tracks the newest stable release. | Most users who want new features as soon as they drop. |
| `ghcr.io/gitsheikhgit/homelab-hub:v1` | Tracks all backwards-compatible updates in the `v1.x` series. | Conservative production setups. |
| `ghcr.io/gitsheikhgit/homelab-hub:v1.0.0` | Exact immutable release build. Never changes. | Air-gapped or change-controlled environments. |

---

### 📥 How to Pull New Images On-Demand

Because your configuration, custom icons, and bookmarks live in the `./data` volume mount on your host, updating Homelab Hub is **completely safe and zero-downtime**:

#### Method 1: The 1-Line Terminal Command (Recommended)
From your `homelab-hub` folder:
```bash
docker compose pull && docker compose up -d
```
*Docker will download only the changed image layers and immediately restart the container with your configuration intact.*

#### Method 2: From Within the Dashboard UI
1. Click the **⚙️ Settings** icon in the dashboard dock or top bar.
2. Select the **📦 Updates & Versions** tab.
3. Click **🔄 Check for Updates** to query the GitHub Container Registry.
4. If a newer image is detected, click **📥 Pull Image On-Demand** to stream the Docker pull directly into the UI!

#### Method 3: Automated Updates with Watchtower (Optional)
If you want your server to update Homelab Hub automatically in the background:
```yaml
services:
  watchtower:
    image: containrrr/watchtower
    container_name: watchtower
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - WATCHTOWER_CLEANUP=true
      - WATCHTOWER_SCHEDULE=0 0 4 * * *  # Every night at 04:00 AM
```

---

## 📖 Detailed Features & Functions Guide

### 1. 🖥️ Host & System Hardware Telemetry
- **CPU Die Temperatures**: Automatically searches system thermal zones and hardware monitoring paths (`/sys/class/thermal/thermal_zone*` and `/sys/class/hwmon/hwmon*`), supporting AMD `k10temp`, Intel `coretemp`, and ARM `cpu-thermal`.
- **System Load Averages**: Displays 1-minute, 5-minute, and 15-minute system load averages alongside overall CPU utilization percentage.
- **Memory & Swap Breakdown**: Monitors active RAM, buffers/cache, free RAM, and swap usage.
- **Network Interface Speeds**: Real-time throughput meters calculating dynamic KB/s or MB/s speeds across active network interfaces.
- **Hardware Profile Auto-Detection**: Automatically queries DMI/SMBIOS (`/sys/class/dmi/id/*`) to recognize your machine model (e.g. *Lenovo ThinkCentre*, *Dell OptiPlex*, *HP EliteDesk*, *Intel NUC*).

---

### 2. 💾 Storage Center & S.M.A.R.T. Health Telemetry
- **Multi-Drive Telemetry**: Inspects physical NVMe SSDs, SATA SSDs, and HDDs.
- **S.M.A.R.T. Attributes**: Reads drive temperature, power-on hours, lifetime power cycles, written gigabytes/terabytes, and flags bad/reallocated sectors.
- **Auto-Discovery of Mounts**: 1-click auto-detection probes all active Linux mountpoints (`/`, `/mnt/*`, `/media/*`) and adds them to your monitoring pool.
- **SSD Garbage Collector**: A visual cleanup drawer that scans your primary drive for safe disk recovery opportunities:
  - Docker builder cache and dangling image layers
  - Old systemd journal log archives (`journalctl --vacuum-time=7d`)
  - Linux apt/dnf package cache archives
  - Temporary files in `/tmp` and `/var/tmp`

---

### 3. 🐳 Docker Fleet Manager & Update Sentinel
- **Container Lifecycle Controls**: Inspect container names, image tags, published port bindings, and uptime statuses. Send `start`, `stop`, or `restart` signals with real-time feedback.
- **Registry Update Sentinel**: Background poller checks remote Docker registries (Docker Hub, GHCR, Quay) to detect if newer image digests exist.
- **Self-Healing Broken Containers**: 1-click button restarts containers currently in an unhealthy or error state.
- **Docker Cache Pruner**: Cleans unused containers, dangling networks, and build caches directly from the UI (`docker system prune -f`).
- **Application Auto-Discovery**: Probes active container ports, matches them against a built-in dictionary of homelab services, and generates suggested launchpad cards.

---

### 4. ⚡ Quick Apps Launchpad & Bookmarks Engine
- **Drag-and-Drop Reordering**: Rearrange cards freely. Layout and order persist automatically in `data/cards.json`.
- **Categorized Workspaces**: Instant switching between:
  - 🌐 *All Apps*
  - ☁️ *Cloud & Office* (Nextcloud, DocuSeal, Papra, Mail)
  - 🎬 *Media & Entertainment* (Immich, Navidrome, Jellyfin, Plex)
  - ⚙️ *System & DevOps* (Portainer, Cockpit, Pi-hole, Uptime Kuma)
  - 🏠 *Smart Home & IoT* (Home Assistant, Zigbee2MQTT, Node-RED)
- **Dual-Link Resolution (LAN vs Remote)**:
  - Each card supports both a **Local LAN URL** (`http://192.168.1.50:9000`) and a **Remote / Tailscale URL** (`http://node.tailnet.ts.net:9000`).
  - Clicking the **LAN / Tailscale mode switch** in the header instantly switches all URLs across the dashboard.
- **Built-In Icon Library**: Includes 40+ high-resolution PNG icons for popular homelab services with support for uploading custom icons.
- **Card Customization**: Add dual buttons per card (e.g. Navidrome Web Player + Librarian Admin).

---

### 5. 🌐 Proxmox VE & Hypervisor Cluster Strip
- **Multi-Node Cluster Strip**: Real-time status cards for Proxmox VE nodes, TrueNAS, Unraid, and Synology NAS systems.
- **Proxmox VM & LXC Console Drawer**: View all virtual machines and containers across nodes. Inspect allocated vCPUs, RAM, running state, and guest IP addresses.
- **Remote VM Power Actions**: Send start, stop, and graceful ACPI shutdown commands to VMs and LXCs directly from the dashboard.
- **Proxmox Backup Server (PBS)**: Displays backup datastore usage, active deduplication ratios, and nightly backup task statuses.

---

### 6. 📅 Homelab Maintenance Agenda & Energy Ledger
- **Maintenance Calendar**: Displays upcoming cron jobs, scheduled snapshot tasks, and self-tests.
- **Energy Cost Tracking**: Calculates daily estimated kilowatt-hours (kWh) consumed by your server and estimates electricity costs based on your configurable local utility tariff ($/kWh).
- **Outbound RFC 5545 `.ics` Feed**: Subscribe on your iPhone, Mac, Android, Google Calendar, or Outlook:
  - `http://<SERVER_IP>:8095/api/calendar/feed.ics`

---

### 7. 🎨 Themes & Customization
- **Sleek Glassmorphism**: Tailored HSL color palette with backdrop blur filters and responsive CSS grid.
- **Theme Switcher**: Instant switching between dark and light modes.
- **Wallpaper Engine**: Upload custom backgrounds, adjust background brightness (0–100%), and configure blur intensity.
- **Omni Search Bar**: Search the web directly from your dashboard using Google, DuckDuckGo, Brave, or Bing.

---

## ⚙️ Full Configuration Reference

### Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `PORT` | `8095` | Port the dashboard webserver binds to inside the container. |
| `RUNNING_IN_DOCKER` | `1` | Informs the Python app to execute `smartctl` directly as root without `sudo`. |
| `HOST_PROC` | `/host/proc` | Host `/proc` filesystem mount for reading host CPU load and RAM. |
| `HOST_SYS` | `/host/sys` | Host `/sys` filesystem mount for reading thermal sensors and DMI data. |
| `TAILSCALE_DOMAIN` | `""` | Optional MagicDNS domain name for automatic remote link generation. |
| `PROXMOX_TOKENS` | `""` | Optional JSON array for Proxmox API tokens via environment variable. |

---

### `data/settings.json` Configuration Reference

All dashboard configurations are stored in `data/settings.json`. If this file does not exist, Homelab Hub automatically creates it using [`data/settings.json.example`](file:///home/cloud/server-dashboard/data/settings.json.example):

```json
{
  "theme": "dark",
  "server_name": "Homelab Hub",
  "lan_host": "192.168.1.100",
  "tailscale_domain": "my-server.ts.net",
  "elec_rate_kwh": 0.23,
  "monitored_drives": [
    {
      "id": "drive_root",
      "name": "System Root SSD",
      "mount": "/",
      "dev": "/dev/sda"
    }
  ],
  "proxmox_tokens": [
    {
      "host": "192.168.1.100",
      "node_id": "pve",
      "nodename": "pve",
      "token": "root@pam!DashboardToken",
      "secret": "your-api-secret-token"
    }
  ]
}
```

---

### Hardware Access Security Model

Homelab Hub requires raw hardware access to read S.M.A.R.T. registers and CPU thermal zones:

| Mode | Configuration | Security Surface |
| :--- | :--- | :--- |
| **Privileged (Simplest)** | `privileged: true` | Grants access to `/dev/sd*` and `/dev/nvme*` for ATA/SCSI passthrough. Recommended for trusted local homelabs. |
| **Granular Capabilities** | `cap_add: [SYS_RAWIO, SYS_ADMIN]` + explicit `devices:` | Limits container privileges strictly to specified disk block devices. |

To use granular capabilities instead of `privileged: true`, edit `docker-compose.yml`:
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

---

## 📡 API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/stats` | Full hardware telemetry (CPU, RAM, temp, network, drives, containers, Proxmox). |
| `GET` | `/api/cards` | Retrieve all custom application launchpad cards. |
| `POST` | `/api/cards` | Create a new application card. |
| `PUT` | `/api/cards/<id>` | Update an existing application card. |
| `DELETE` | `/api/cards/<id>` | Delete an application card. |
| `GET` | `/api/cards/auto-detect` | Scan local Docker daemon and propose new application cards. |
| `POST` | `/api/cards/auto-create` | Batch import proposed Docker application cards. |
| `GET` | `/api/settings` | Retrieve user dashboard appearance, layout, and widget configuration. |
| `POST` | `/api/settings` | Save modified dashboard settings. |
| `GET` | `/api/drives/detect` | Probe system mounts and suggest drives for S.M.A.R.T. monitoring. |
| `POST` | `/api/drives/config` | Update monitored disk and mount configuration. |
| `POST` | `/api/run-smart-diagnostic`| Trigger an immediate S.M.A.R.T. diagnostic check across all drives. |
| `POST` | `/api/docker/control` | Control Docker container state (`action`: `start` / `stop` / `restart`). |
| `POST` | `/api/docker/prune` | Execute Docker system cache prune. |
| `POST` | `/api/proxmox/control` | Send VM/LXC power commands (`action`: `start` / `stop` / `shutdown`). |
| `GET` | `/api/calendar/feed.ics` | Live RFC 5545 iCalendar feed subscription. |
| `GET` | `/api/weather` | Current weather and forecast for configured coordinates. |

---

## 🛡️ Security & Privacy

- **Zero Analytics & Trackers**: No external telemetry, tracking scripts, or cloud phone-home mechanisms.
- **Local Key Storage**: All API tokens and passwords remain strictly on your server in `data/settings.json`.
- **Git Protection**: The provided `.gitignore` automatically prevents personal credentials, local IPs, and diagnostic caches from being committed.

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
