# 📜 Changelog

All notable changes to **Homelab Hub** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [[v1.1.1](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.1.1)] - 2026-09-24

### Fixed
- **Docker Container In-Place Recreation & 1-Click Update**: Fixed issue where container updates repeatedly showed "Update Available" because standalone containers or containers without accessible compose files were only restarted instead of being recreated with the newly pulled image. Implemented robust native container recreation preserving all volumes, mounts, ports, environment variables, restart policies, labels, and networks, with automatic rollback protection.
- **Dynamic Portainer vs. Docker Fleet Adapter**: Widget dynamically detects whether Portainer is running. If not installed/running, dynamically switches to "Docker Fleet & Containers" with "Containers ↗" opening the container manager drawer instead of attempting to load unreachable port `:9000`.
- **Conditional Tailscale Visibility**: Automatically hides the `#widget_tailscale` card and the top bar `[🔒 Tailscale Remote]` button on systems where Tailscale is unconfigured or disabled in settings.
- **Remote Host Container Link Resolution**: Added dynamic URL hostname resolution (`resolveAppUrl`) across all container badges and drawer action links, ensuring links point to the server's real LAN IP rather than `127.0.0.1` or `localhost` when accessed from client devices.
- **Dynamic Agenda Tasks & System Automation**: Replaced hardcoded static HTML tasks with dynamic persistence backed by `/api/tasks` and host timer auto-detection via `systemctl list-timers`.
- **Energy Meter Telemetry Precision**: Eliminated premature rounding in energy calculations that trapped daily kWh and runtime hours at zero.

---

## [[v1.1.0](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.1.0)] - 2026-09-20

### Added
- **Beszel-Style Live Silicon & Hardware Telemetry Waveforms**: High-resolution, continuous SVG/Canvas waveform graphs for CPU utilization, Memory allocation, Network throughput (download/upload), and Disk I/O (read/write) with real-time 60 FPS rendering and 1m, 2m, 5m, and 10m time-window presets.
- **Interactive Crosshair & Hover Scrubbing**: Live coordinate tracking across all waveform timelines showing precise timestamps, CPU %, memory metrics, and I/O rates.
- **Docker Container Resource Utilization Matrix**: Real-time per-container CPU percentage and RAM usage/limit allocation table with instant text search filtering and sorting by CPU, RAM, or Name.
- **Pinned Diagnostic Metrics & Tab Navigation**: Host Silicon & Telemetry modal features pinned glance metrics (CPU load/frequency, memory usage/cached, network throughput, disk operations) and sticky tab navigation that remain accessible while scrolling through detailed diagnostics.
- **1-Second Real-Time Telemetry Streaming Engine**: Ultra-low-latency, zero-drift background collector streaming host and container performance deltas without synthetic jitter or artificial sawtooth offsets.

### Changed
- **Universal Theme Contrast & Visibility**: Perfected light and dark mode contrast across the sticky mobile masthead, initial setup wizard option buttons, and diagnostic modal overlays, guaranteeing WCAG AAA compliance (> 7:1 contrast ratio) in both themes.
- **Z-Index Layering & Occlusion Prevention**: Elevated cluster node dropdown menus, widget 3-dot action popups, and modal drawer overlays (`z-index: 9999`) to prevent clipping or background obstruction by adjacent cards.

---

## [[v1.0.9](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.9)] - 2026-09-20

### Added
- **Automated Operational History & Telemetry Ledger**: Automatic background recording of system startup events, speedtest benchmarks, Docker fleet discoveries, storage diagnostics, and finalized midnight energy consumption ledgers in the Date Inspector timeline.
- **Universal Multi-Tier Speedtest Engine**: Benchmark engine functions natively across all Linux distributions, Docker containers, VMs, and architectures (x86_64, ARM, Raspberry Pi) with zero dependency on external CLI binaries.
- **Deep-Link URL Category & Date Navigation**: Added support for `?category=` (`services`, `storage`, `docker`, `agenda`, `proxmox`) and `?inspect=YYYY-MM-DD` query parameters for instant deep-linking.

### Changed
- **Complete Mobile Viewport & Card Optimization**: Solved horizontal overflow and cut-off card boundaries on smartphones (iPhone / Android) with `min-width: 0` constraints, auto-wrapping headers (`.card-head-left`, `.card-head-right`), and adaptive metric cells.
- **Unified 3-Metric Single-Row App Layout**: Dynamic application cards (`Status`, `Category`, `Port`) and Portainer stacks (`Running`, `Stopped`, `Total`) now fit into a clean single row on mobile with 33.3% flex distribution without line wrapping or edge clipping.
- **Dynamic Proxmox UI Visibility**: The `🖥️ Proxmox` filter tab, `VMs / PVE` dock button, and `Proxmox Cluster & VMs` card are now completely dynamic and automatically hide on fresh installations or non-hypervisor systems unless Proxmox VE or cluster nodes are actively configured.
- **Complete Cross-System Sanitization**: Cleaned historical IPs, personal cards, and starting energy ledger metrics from defaults so any fresh setup starts with a true zero baseline.

---

## [[v1.0.8](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.8)] - 2026-09-19

### Added
- **Proxmox Hypervisor VMs & Containers Overhaul**: Live telemetry caching and populated real-time status, vCPU, RAM, CPU %, and LAN IPs for all 13 cluster guests across nodes `pve` and `pve2`.
- **Proxmox Power Controls & Instant Refresh**: Direct 1-click power management (Start, Stop, Reboot) with auto-detection for LXC vs QEMU, live search filtering, guest category tabs, and on-demand `/api/proxmox/refresh`.
- **Dynamic System Tasks**: Integrated `task_manager.py` with `/api/system/tasks` to dynamically manage host maintenance and systemd timers.
- **Setup Wizard Clean Replacement**: Added `[✓] Clean Setup: Replace existing cards` checkbox to wizard footer so fresh setups cleanly replace old cards instead of creating duplicates.
- **Dynamic Initial Monogram Fallbacks**: Added glowing initials badges for any apps without custom icons.

### Fixed
- **Docker Detection & Reachable Host IP**: Container URL resolution binds to the client's reachable host/LAN IP (`192.168.0.8`) instead of internal Docker bridge IPs (`172.16.x.x`–`172.31.x.x`).
- **Bypass Cache on Manual Update Check**: Added `?force=1` on manual "Check for Updates" queries to bypass server-side caches and query GitHub directly.

---

## [[v1.0.7](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.7)] - 2026-09-19

### Added
- **Docker Fleet CLI Inside Container**: Bundled `docker-cli` in `Dockerfile` so the `/usr/bin/docker` client binary queries `/var/run/docker.sock` and displays running containers inside containerized deployments.
- **Fresh Install Dynamic Discovery**: On fresh installations on any new system, Homelab Hub automatically scans the local Docker engine and auto-populates cards for the containers *actually running* on that specific host.
- **Clean Initial Setup State**: When no containers or cards exist, the dashboard presents a clean onboarding prompt with one-click **⚡ Auto-Detect Docker Apps** and **➕ Add Card Manually** actions.
- **Automated 1-Click Update & Restart**: Added `/api/system/apply-update` and UI button **⚡ Update & Restart Now** that downloads updates, restarts the service, and automatically reconnects the browser with zero terminal commands.

### Security
- **Build Isolation & Sanitization**: Strengthened `.dockerignore` to prevent local configuration (`cards.json`, `settings.json`, `calendar_events.json`) from ever being copied into Docker images. Cleaned personal container names from fallback dictionaries.

---

## [[v1.0.6](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.6)] - 2026-09-19

### Added
- **Running Version Header Badge**: Live version pill (`v1.0.6`) directly on the top dashboard header next to the brand title. Clicking it jumps directly to the updates panel.
- **Automated Update Availability Flag**: Automatic background update polling against GitHub releases. If a newer image/release is published, a glowing update badge (`Update Available: vX.Y.Z`) appears on the header and an amber alert indicator appears on the Settings button.
- **Semver Precision & Cache Guard**: Upgraded `/api/system/update-check` with semver comparison and a 15-minute in-memory cache to prevent GitHub API rate limiting.
- **Menu Drawer Version Entry**: Integrated version and update status into the navigation drawer menu.

---

## [[v1.0.5](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.5)] - 2026-09-19

### Fixed
- **Fixed Docker Fleet Counts**: Resolved duplicate element IDs that caused container count metrics (`Running`, `Stopped`, `Total`) to remain blank (`--`) on companion cards.
- **Portainer Portal Direct Navigation**: Clicking the Portainer card opens Portainer's web UI portal directly via configured LAN port `:9000` or Tailscale remote URL.
- **Privacy & Location Hardening**: Replaced all hardcoded local township fallbacks in `app.py` and `templates/index.html` with generic metropolitan defaults.

---

## [[v1.0.4](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.4)] - 2026-09-19

### Changed
- **Calendar & Clock Visibility Overhaul**: Completely eliminated hardcoded dark background bands in Light Mode; replaced with soft slate themed surfaces (`#f8fafc`).
- **High-Contrast Typography**: Converted digital time to bold dark slate (`#0f172a`, weight `800`) and date subtitles to deep slate (`#475569`).
- **Energy Ledger Contrast**: Replaced low-contrast yellow text with warm amber pill badges (`#92400e` text on `#fef3c7` pill with `#fde68a` border).
- **Today Highlight**: Replaced washed-out cell styles with a solid royal blue pill (`#2563eb`), crisp white numerals (`#ffffff`), and a highlighted cost badge.

---

## [[v1.0.3](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.3)] - 2026-09-19

### Changed
- **GitHub Image Cache Busting**: Renamed screenshot assets to `real_homelab_dark.png` and `real_homelab_light.png` and added cache-busting version query parameters (`?v=3`).

---

## [[v1.0.2](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.2)] - 2026-09-19

### Added
- **Authentic Dashboard Captures**: Replaced all synthetic AI mockups with real browser captures taken directly from the live running server dashboard in both Dark and Light modes.
- **Light Mode UI System**: Overhauled Hypervisor node pills, navigation dock (`.mobile-bottom-nav`), segmented network mode switch (LAN vs Tailscale), and service tags for high contrast.
- **Demo Masking Mode**: Implemented client-side `?demo=1` parameter to sanitize cluster node IPs and weather headers during public screenshot captures.

---

## [[v1.0.1](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.1)] - 2026-09-19

### Changed
- **Initial Contrast Adjustments**: Improved light mode contrast for select cards and added the initial UI showcase gallery.

---

## [[v1.0.0](https://github.com/gitsheikhgit/homelab-hub/releases/tag/v1.0.0)] - 2026-09-19

### Added
- **Initial Public Release**: Comprehensive server management and hardware telemetry dashboard for homelabs. Deep hardware sensing, Proxmox VE integration, Docker fleet controls, energy tracking ledger, and self-hosted application launchpad.
