#!/usr/bin/env python3
"""
Card & Settings Manager for Homelab Dashboard
Handles persistent storage of application cards, icons, custom wallpaper uploads,
and dashboard configuration.
"""

import os
import json
import uuid
import time
import subprocess
import re
import socket
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CARDS_FILE = os.path.join(DATA_DIR, "cards.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
ICONS_DIR = os.path.join(BASE_DIR, "static", "icons")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
UPLOAD_ICONS_DIR = os.path.join(UPLOAD_DIR, "icons")
UPLOAD_WALLPAPERS_DIR = os.path.join(UPLOAD_DIR, "wallpapers")

# Ensure required directories exist
for d in [DATA_DIR, UPLOAD_DIR, UPLOAD_ICONS_DIR, UPLOAD_WALLPAPERS_DIR]:
    os.makedirs(d, exist_ok=True)

DEFAULT_CARDS = []

DEFAULT_SETTINGS = {
    "search_provider": "google",
    "search_providers": {
        "google": {"name": "Google", "url": "https://www.google.com/search?q=", "icon": "🌐"},
        "duckduckgo": {"name": "DuckDuckGo", "url": "https://duckduckgo.com/?q=", "icon": "🦆"},
        "brave": {"name": "Brave", "url": "https://search.brave.com/search?q=", "icon": "🦁"},
        "bing": {"name": "Bing", "url": "https://www.bing.com/search?q=", "icon": "🔍"}
    },
    "wallpaper": "",
    "wallpaper_type": "default",
    "wallpaper_blur": 0,
    "wallpaper_brightness": 0.95,
    "dock_position": "bottom",
    "theme": "dark",
    "initial_setup_completed": False,
    "server_name": "",
    "widgets": {
        "calendar": True,
        "host_overview": True,
        "host_power": True,
        "proxmox": False,
        "portainer": False,
        "cluster_nodes_strip": False,
        "tailscale": False,
        "storage": True,
        "ssd_cleaner": True,
        "speedtest": True,
        "media_row": True
    },
    "cluster_nodes": [],
    "service_cards": [],
    "proxmox_nodes": [],
    "proxmox_tokens": [],
    "widgets_layout": {
        "col1": ["cards_apps"],
        "col2": ["widget_calendar", "widget_host_overview", "widget_host_power"],
        "col3": ["widget_portainer", "widget_tailscale", "widget_storage", "widget_ssd_cleaner", "widget_speedtest"]
    },
    "quick_icon_size_px": 34,
    "portainer_config": {
        "title": "Portainer CE",
        "subtitle": "Docker Container Fleet",
        "lan_url": "",
        "ts_url": "",
        "click_action": "drawer"
    },
    "monitored_drives": [],
    "lan_host": "",
    "tailscale_domain": "",
    "tailscale_ip": "",
    "elec_rate_kwh": 0.23,
    "base_platform_watts": 13.5
}

def get_cards():
    """Retrieve list of cards. On fresh installations with no cards.json, returns an empty list so user sets up cleanly."""
    if os.path.exists(CARDS_FILE):
        try:
            with open(CARDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_cards(cards):
    """Save cards list to cards.json."""
    try:
        with open(CARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving cards: {e}")
        return False

def add_card(data):
    """Add a new application card."""
    cards = get_cards()
    card_id = "card_" + uuid.uuid4().hex[:8]
    name = data.get("name", "New App").strip()
    container_name = data.get("container_name", "").strip()
    icon = data.get("icon", "").strip()
    
    # Auto-resolve accurate icon if missing or left on generic placeholder
    if not icon or (icon in ("/static/icons/portainer.png", "/static/icons/cockpit.png", "/static/icons/casaos.png") and "portainer" not in (name + " " + container_name).lower()):
        resolved = resolve_app_icon(name, container_name)
        if resolved and resolved != "/static/icons/casaos.png":
            icon = resolved
        elif not icon:
            icon = resolved or "/static/icons/portainer.png"

    new_card = {
        "id": card_id,
        "name": name,
        "subtitle": data.get("subtitle", "").strip(),
        "lan_url": data.get("lan_url", "").strip(),
        "ts_url": data.get("ts_url", "").strip(),
        "second_link_name": data.get("second_link_name", "").strip(),
        "second_lan_url": data.get("second_lan_url", "").strip(),
        "second_ts_url": data.get("second_ts_url", "").strip(),
        "icon": icon,
        "category": data.get("category", "Apps").strip() or "Apps",
        "order": len(cards) + 1
    }
    cards.append(new_card)
    save_cards(cards)
    return new_card

def update_card(card_id, data):
    """Update an existing card."""
    cards = get_cards()
    found = False
    for i, c in enumerate(cards):
        if c.get("id") == card_id:
            cards[i]["name"] = data.get("name", c.get("name")).strip()
            cards[i]["subtitle"] = data.get("subtitle", c.get("subtitle")).strip()
            cards[i]["lan_url"] = data.get("lan_url", c.get("lan_url")).strip()
            cards[i]["ts_url"] = data.get("ts_url", c.get("ts_url")).strip()
            cards[i]["second_link_name"] = data.get("second_link_name", c.get("second_link_name", "")).strip()
            cards[i]["second_lan_url"] = data.get("second_lan_url", c.get("second_lan_url", "")).strip()
            cards[i]["second_ts_url"] = data.get("second_ts_url", c.get("second_ts_url", "")).strip()
            
            icon = data.get("icon", c.get("icon", "")).strip()
            if not icon or (icon in ("/static/icons/portainer.png", "/static/icons/cockpit.png", "/static/icons/casaos.png") and "portainer" not in cards[i]["name"].lower()):
                resolved = resolve_app_icon(cards[i]["name"], "")
                if resolved and resolved != "/static/icons/casaos.png":
                    icon = resolved
            cards[i]["icon"] = icon or c.get("icon") or "/static/icons/portainer.png"
            cards[i]["category"] = data.get("category", c.get("category", "Apps")).strip() or "Apps"
            if "order" in data:
                try:
                    cards[i]["order"] = int(data["order"])
                except Exception:
                    pass
            found = True
            break
    if found:
        save_cards(cards)
        return {"status": "success", "card": cards[i]}
    return {"status": "error", "message": f"Card {card_id} not found"}

def delete_card(card_id):
    """Delete a card by ID."""
    cards = get_cards()
    initial_len = len(cards)
    cards = [c for c in cards if c.get("id") != card_id]
    if len(cards) < initial_len:
        save_cards(cards)
        return {"status": "success", "deleted_id": card_id}
    return {"status": "error", "message": f"Card {card_id} not found"}

def reorder_cards(card_ids):
    """Reorder cards based on a list of card IDs and persist to cards.json."""
    cards = get_cards()
    card_map = {c.get("id"): c for c in cards}
    reordered = []
    for idx, cid in enumerate(card_ids, start=1):
        if cid in card_map:
            card = card_map.pop(cid)
            card["order"] = idx
            reordered.append(card)
    for card in card_map.values():
        card["order"] = len(reordered) + 1
        reordered.append(card)
    save_cards(reordered)
    return reordered

def get_settings():
    """Retrieve dashboard settings, merging missing defaults."""
    res = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                res.update(loaded)
                for key in ("widgets", "widgets_layout", "search_providers", "portainer_config"):
                    if key in DEFAULT_SETTINGS and isinstance(DEFAULT_SETTINGS[key], dict):
                        merged = dict(DEFAULT_SETTINGS[key])
                        if key in loaded and isinstance(loaded[key], dict):
                            merged.update(loaded[key])
                        res[key] = merged
                if "cluster_nodes" not in loaded or not isinstance(loaded["cluster_nodes"], list):
                    res["cluster_nodes"] = list(DEFAULT_SETTINGS["cluster_nodes"])
                if "service_cards" not in loaded or not isinstance(loaded["service_cards"], list):
                    res["service_cards"] = list(DEFAULT_SETTINGS["service_cards"])
                if "monitored_drives" not in loaded or not isinstance(loaded["monitored_drives"], list):
                    res["monitored_drives"] = list(DEFAULT_SETTINGS["monitored_drives"])
                if "quick_icon_size_px" not in loaded:
                    res["quick_icon_size_px"] = DEFAULT_SETTINGS["quick_icon_size_px"]
                return res
        except Exception:
            pass
    save_settings(DEFAULT_SETTINGS)
    return DEFAULT_SETTINGS

def save_settings(settings):
    """Save dashboard settings."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False

def get_available_icons():
    """Return all available icons (built-in + uploaded)."""
    icons = []
    # 1. Built-in icons from static/icons/
    if os.path.exists(ICONS_DIR):
        for fname in sorted(os.listdir(ICONS_DIR)):
            if fname.lower().endswith(('.png', '.svg', '.jpg', '.jpeg', '.webp')):
                name = os.path.splitext(fname)[0].capitalize()
                icons.append({
                    "name": name,
                    "filename": fname,
                    "url": f"/static/icons/{fname}",
                    "type": "builtin"
                })
    # 2. User uploaded icons
    if os.path.exists(UPLOAD_ICONS_DIR):
        for fname in sorted(os.listdir(UPLOAD_ICONS_DIR)):
            if fname.lower().endswith(('.png', '.svg', '.jpg', '.jpeg', '.webp')):
                name = os.path.splitext(fname)[0].replace("_", " ").capitalize()
                icons.append({
                    "name": name,
                    "filename": fname,
                    "url": f"/uploads/icons/{fname}",
                    "type": "uploaded"
                })
    return icons

def save_uploaded_icon(file_storage):
    """Save an uploaded custom icon file."""
    if not file_storage or not file_storage.filename:
        return None
    raw_name = secure_filename(file_storage.filename)
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in ('.png', '.svg', '.jpg', '.jpeg', '.webp'):
        return None
    filename = f"icon_{int(time.time())}_{raw_name}"
    filepath = os.path.join(UPLOAD_ICONS_DIR, filename)
    file_storage.save(filepath)
    return f"/uploads/icons/{filename}"

def save_uploaded_wallpaper(file_storage):
    """Save an uploaded wallpaper image file."""
    if not file_storage or not file_storage.filename:
        return None
    raw_name = secure_filename(file_storage.filename)
    ext = os.path.splitext(raw_name)[1].lower()
    if ext not in ('.png', '.jpg', '.jpeg', '.webp'):
        return None
    filename = f"wallpaper_{int(time.time())}{ext}"
    filepath = os.path.join(UPLOAD_WALLPAPERS_DIR, filename)
    file_storage.save(filepath)
    return f"/uploads/wallpapers/{filename}"


# ── Automated Docker Application Discovery & Batch Creation ──

KNOWN_APP_DEFINITIONS = {
    "musicgrabber": {
        "name": "MusicGrabber",
        "subtitle": "High-Fidelity Audio Downloader",
        "category": "Media",
        "icon": "/static/icons/musicgrabber.png"
    },
    "navidrome": {
        "name": "Navidrome",
        "subtitle": "Lossless Music Streaming Core",
        "category": "Media",
        "icon": "/static/icons/navidrome.png"
    },
    "immich": {
        "name": "Immich Photos",
        "subtitle": "Self-Hosted Photo & Video Vault",
        "category": "Media",
        "icon": "/static/icons/immich.png"
    },
    "nextcloud": {
        "name": "Nextcloud Hub",
        "subtitle": "Cloud Storage & Collaboration",
        "category": "Cloud & Office",
        "icon": "/static/icons/nextcloud.png",
        "second_link_name": "Admin"
    },
    "docuseal": {
        "name": "DocuSeal Signatures",
        "subtitle": "Digital Document Signing Platform",
        "category": "Cloud & Office",
        "icon": "/static/icons/docuseal.png"
    },
    "stirling": {
        "name": "Stirling-PDF",
        "subtitle": "All-in-One Local PDF Tools",
        "category": "Cloud & Office",
        "icon": "/static/icons/stirling.png"
    },
    "papra": {
        "name": "Papra AI Documents",
        "subtitle": "AI OCR Document Management",
        "category": "Cloud & Office",
        "icon": "/static/icons/papra.png"
    },
    "portainer": {
        "name": "Portainer CE",
        "subtitle": "Docker Container Management",
        "category": "System",
        "icon": "/static/icons/portainer.png"
    },
    "syncthing": {
        "name": "Syncthing",
        "subtitle": "Continuous Decentralized File Sync",
        "category": "Cloud & Office",
        "icon": "/static/icons/syncthing.png"
    },
    "homeassistant": {
        "name": "Home Assistant",
        "subtitle": "Smart Home & Automation Hub",
        "category": "Smart Home",
        "icon": "/static/icons/homeassistant.png"
    },
    "adguard": {
        "name": "AdGuard Home",
        "subtitle": "Network-Wide Ad & Tracker Blocker",
        "category": "Security",
        "icon": "/static/icons/adguard.png"
    },
    "pihole": {
        "name": "Pi-hole DNS",
        "subtitle": "DNS Sinkhole & Ad Blocker",
        "category": "Security",
        "icon": "/static/icons/pihole.png"
    },
    "casaos": {
        "name": "CasaOS Dashboard",
        "subtitle": "Simple Home Cloud System",
        "category": "System",
        "icon": "/static/icons/casaos.png"
    },
    "cockpit": {
        "name": "Cockpit Console",
        "subtitle": "Linux Server Administration",
        "category": "System",
        "icon": "/static/icons/cockpit.png"
    },
    "vaultwarden": {
        "name": "Vaultwarden",
        "subtitle": "Self-Hosted Password Vault",
        "category": "Security",
        "icon": "/static/icons/vaultwarden.png"
    },
    "uptime-kuma": {
        "name": "Uptime Kuma",
        "subtitle": "Self-Hosted Service Monitor",
        "category": "System",
        "icon": "/static/icons/uptime-kuma.png"
    },
    "jellyfin": {
        "name": "Jellyfin Media",
        "subtitle": "Free Software Media System",
        "category": "Media",
        "icon": "/static/icons/jellyfin.png"
    },
    "plex": {
        "name": "Plex Media Server",
        "subtitle": "Personal Media Streaming Server",
        "category": "Media",
        "icon": "/static/icons/plex.png"
    },
    "ollama": {
        "name": "Ollama LLM",
        "subtitle": "Local Artificial Intelligence Model API",
        "category": "System",
        "icon": "/static/icons/ollama.png"
    },
    "open-webui": {
        "name": "Open WebUI",
        "subtitle": "User-Friendly AI Chat Interface",
        "category": "System",
        "icon": "/static/icons/open-webui.png"
    },
    "speedtest": {
        "name": "Speedtest Tracker",
        "subtitle": "Bandwidth & WAN Latency Monitor",
        "category": "System",
        "icon": "/static/icons/speedtest.png"
    },
    "snappymail": {
        "name": "SnappyMail",
        "subtitle": "Fast Webmail Client",
        "category": "Cloud & Office",
        "icon": "/static/icons/snappymail.png"
    },
    "roundcube": {
        "name": "Roundcube Webmail",
        "subtitle": "Browser-Based Email Platform",
        "category": "Cloud & Office",
        "icon": "/static/icons/roundcube.png"
    },
    "mailcow": {
        "name": "Mailcow UI",
        "subtitle": "Complete Mail Server Suite",
        "category": "Cloud & Office",
        "icon": "/static/icons/mailcow.png"
    },
    "crowdsec": {
        "name": "CrowdSec Security",
        "subtitle": "Collaborative Intrusion Prevention Engine",
        "category": "Security",
        "icon": "/static/icons/crowdsec.png"
    },
    "truenas": {
        "name": "TrueNAS Core",
        "subtitle": "Network Attached Storage Management",
        "category": "System",
        "icon": "/static/icons/truenas.png"
    },
    "unraid": {
        "name": "Unraid OS",
        "subtitle": "Modular Storage & Hypervisor OS",
        "category": "System",
        "icon": "/static/icons/unraid.png"
    },
    "synology": {
        "name": "Synology DSM",
        "subtitle": "DiskStation Storage Management",
        "category": "System",
        "icon": "/static/icons/synology.png"
    },
    "qnap": {
        "name": "QNAP QTS",
        "subtitle": "Turbo NAS Operating Platform",
        "category": "System",
        "icon": "/static/icons/qnap.png"
    },
    "tailscale": {
        "name": "Tailscale Admin",
        "subtitle": "Zero-Config Mesh VPN Control",
        "category": "Security",
        "icon": "/static/icons/tailscale.png"
    },
    "tor": {
        "name": "Tor Relay",
        "subtitle": "Onion Routing & Privacy Gateway",
        "category": "Security",
        "icon": "/static/icons/tor.png"
    },
    "musicbrainz": {
        "name": "MusicBrainz Picard",
        "subtitle": "Music Metadata & Tagging Mirror",
        "category": "Media",
        "icon": "/static/icons/musicbrainz.png"
    },
    "cpanel": {
        "name": "cPanel Portal",
        "subtitle": "Web Hosting & Domain Console",
        "category": "System",
        "icon": "/static/icons/cpanel.png"
    },
    "hestia": {
        "name": "HestiaCP",
        "subtitle": "Lightweight Web Server Control Panel",
        "category": "System",
        "icon": "/static/icons/hestia.png"
    },
    "proxmox": {
        "name": "Proxmox VE",
        "subtitle": "Enterprise Virtualization Hypervisor",
        "category": "System",
        "icon": "/static/icons/proxmox.png"
    },
    "pbs": {
        "name": "Proxmox Backup Server",
        "subtitle": "Enterprise Deduplicating Backup Suite",
        "category": "System",
        "icon": "/static/icons/pbs.png"
    },
    "academy": {
        "name": "Academy Learning Hub",
        "subtitle": "Self-Hosted Learning & Education Platform",
        "category": "Cloud & Office",
        "icon": "/static/icons/academy.png"
    },
    "meetings": {
        "name": "Jitsi Video Meetings",
        "subtitle": "Private Encrypted Video Conferencing",
        "category": "Cloud & Office",
        "icon": "/static/icons/meetings.png"
    },
    "zoom": {
        "name": "Zoom Meetings",
        "subtitle": "Web Conferencing Client",
        "category": "Cloud & Office",
        "icon": "/static/icons/zoom.png"
    },
    "rspamd": {
        "name": "Rspamd Anti-Spam",
        "subtitle": "Advanced Email Filtering & Security",
        "category": "Security",
        "icon": "/static/icons/rspamd.png"
    },
    "duckduckgo": {
        "name": "Private Search Engine",
        "subtitle": "Metasearch Gateway & Privacy Browser",
        "category": "Cloud & Office",
        "icon": "/static/icons/duckduckgo.png"
    },
    "esxi": {
        "name": "VMware ESXi",
        "subtitle": "Bare-Metal Virtualization Hypervisor",
        "category": "System",
        "icon": "/static/icons/esxi.png"
    }
}

def resolve_app_icon(c_name, c_img):
    """Dynamically determine the most accurate icon URL for any container or image."""
    c_low = (str(c_name or '') + " " + str(c_img or '')).lower()

    # 1. Check known app definitions
    for key, meta in KNOWN_APP_DEFINITIONS.items():
        if key in c_low:
            return meta["icon"]

    # 2. Semantic matching across all 42 available static icons
    semantic_map = [
        ("spiderscan", "/static/icons/spiderscan.png"),
        ("spiderfoot", "/static/icons/spiderscan.png"),
        ("privacy", "/static/icons/spiderscan.png"),
        ("musicgrabber", "/static/icons/musicgrabber.png"),
        ("navidrome", "/static/icons/navidrome.png"),
        ("subsonic", "/static/icons/navidrome.png"),
        ("airsonic", "/static/icons/navidrome.png"),
        ("ampache", "/static/icons/navidrome.png"),
        ("funkwhale", "/static/icons/navidrome.png"),
        ("music", "/static/icons/musicgrabber.png"),
        ("audio", "/static/icons/navidrome.png"),
        ("sound", "/static/icons/navidrome.png"),
        ("radio", "/static/icons/navidrome.png"),
        ("spotdl", "/static/icons/musicgrabber.png"),
        ("deezloader", "/static/icons/musicgrabber.png"),
        ("torrent", "/static/icons/musicgrabber.png"),
        ("qbittorrent", "/static/icons/musicgrabber.png"),
        ("transmission", "/static/icons/musicgrabber.png"),
        ("deluge", "/static/icons/musicgrabber.png"),
        ("immich", "/static/icons/immich.png"),
        ("photoprism", "/static/icons/immich.png"),
        ("photo", "/static/icons/immich.png"),
        ("gallery", "/static/icons/immich.png"),
        ("image", "/static/icons/immich.png"),
        ("jellyfin", "/static/icons/jellyfin.png"),
        ("emby", "/static/icons/jellyfin.png"),
        ("plex", "/static/icons/plex.png"),
        ("video", "/static/icons/jellyfin.png"),
        ("movie", "/static/icons/plex.png"),
        ("media", "/static/icons/jellyfin.png"),
        ("stream", "/static/icons/jellyfin.png"),
        ("cinema", "/static/icons/jellyfin.png"),
        ("pdf", "/static/icons/stirling.png"),
        ("stirling", "/static/icons/stirling.png"),
        ("docuseal", "/static/icons/docuseal.png"),
        ("sign", "/static/icons/docuseal.png"),
        ("contract", "/static/icons/docuseal.png"),
        ("paperless", "/static/icons/papra.png"),
        ("papra", "/static/icons/papra.png"),
        ("ocr", "/static/icons/papra.png"),
        ("paper", "/static/icons/papra.png"),
        ("document", "/static/icons/papra.png"),
        ("archive", "/static/icons/papra.png"),
        ("scan", "/static/icons/papra.png"),
        ("mailcow", "/static/icons/mailcow.png"),
        ("roundcube", "/static/icons/roundcube.png"),
        ("snappymail", "/static/icons/snappymail.png"),
        ("rainloop", "/static/icons/snappymail.png"),
        ("mail", "/static/icons/snappymail.png"),
        ("email", "/static/icons/snappymail.png"),
        ("postfix", "/static/icons/mailcow.png"),
        ("rspamd", "/static/icons/rspamd.png"),
        ("spam", "/static/icons/rspamd.png"),
        ("adguard", "/static/icons/adguard.png"),
        ("pihole", "/static/icons/pihole.png"),
        ("dns", "/static/icons/pihole.png"),
        ("block", "/static/icons/adguard.png"),
        ("crowdsec", "/static/icons/crowdsec.png"),
        ("firewall", "/static/icons/crowdsec.png"),
        ("security", "/static/icons/crowdsec.png"),
        ("waf", "/static/icons/crowdsec.png"),
        ("nginx", "/static/icons/crowdsec.png"),
        ("traefik", "/static/icons/crowdsec.png"),
        ("caddy", "/static/icons/crowdsec.png"),
        ("tailscale", "/static/icons/tailscale.png"),
        ("headscale", "/static/icons/tailscale.png"),
        ("wireguard", "/static/icons/tailscale.png"),
        ("zerotier", "/static/icons/tailscale.png"),
        ("netmaker", "/static/icons/tailscale.png"),
        ("vpn", "/static/icons/tailscale.png"),
        ("speedtest", "/static/icons/speedtest.png"),
        ("speed", "/static/icons/speedtest.png"),
        ("bandwidth", "/static/icons/speedtest.png"),
        ("iperf", "/static/icons/speedtest.png"),
        ("uptime", "/static/icons/uptime-kuma.png"),
        ("kuma", "/static/icons/uptime-kuma.png"),
        ("monitor", "/static/icons/uptime-kuma.png"),
        ("statping", "/static/icons/uptime-kuma.png"),
        ("gatus", "/static/icons/uptime-kuma.png"),
        ("beszel", "/static/icons/uptime-kuma.png"),
        ("netdata", "/static/icons/uptime-kuma.png"),
        ("grafana", "/static/icons/uptime-kuma.png"),
        ("ollama", "/static/icons/ollama.png"),
        ("llama", "/static/icons/ollama.png"),
        ("webui", "/static/icons/open-webui.png"),
        ("open-webui", "/static/icons/open-webui.png"),
        ("openwebui", "/static/icons/open-webui.png"),
        ("gpt", "/static/icons/open-webui.png"),
        ("chat", "/static/icons/open-webui.png"),
        ("ai", "/static/icons/open-webui.png"),
        ("bot", "/static/icons/open-webui.png"),
        ("syncthing", "/static/icons/syncthing.png"),
        ("resilio", "/static/icons/syncthing.png"),
        ("btsync", "/static/icons/syncthing.png"),
        ("sync", "/static/icons/syncthing.png"),
        ("nextcloud", "/static/icons/nextcloud.png"),
        ("owncloud", "/static/icons/nextcloud.png"),
        ("seafile", "/static/icons/nextcloud.png"),
        ("cloud", "/static/icons/nextcloud.png"),
        ("drive", "/static/icons/nextcloud.png"),
        ("vaultwarden", "/static/icons/vaultwarden.png"),
        ("bitwarden", "/static/icons/vaultwarden.png"),
        ("passbolt", "/static/icons/vaultwarden.png"),
        ("keepass", "/static/icons/vaultwarden.png"),
        ("password", "/static/icons/vaultwarden.png"),
        ("pass", "/static/icons/vaultwarden.png"),
        ("vault", "/static/icons/vaultwarden.png"),
        ("portainer", "/static/icons/portainer.png"),
        ("docker", "/static/icons/portainer.png"),
        ("tor", "/static/icons/tor.png"),
        ("onion", "/static/icons/tor.png"),
        ("truenas", "/static/icons/truenas.png"),
        ("freenas", "/static/icons/truenas.png"),
        ("unraid", "/static/icons/unraid.png"),
        ("synology", "/static/icons/synology.png"),
        ("qnap", "/static/icons/qnap.png"),
        ("cpanel", "/static/icons/cpanel.png"),
        ("hestia", "/static/icons/hestia.png"),
        ("proxmox", "/static/icons/proxmox.png"),
        ("pve", "/static/icons/proxmox.png"),
        ("pbs", "/static/icons/pbs.png"),
        ("homeassistant", "/static/icons/homeassistant.png"),
        ("hass", "/static/icons/homeassistant.png"),
        ("home", "/static/icons/homeassistant.png"),
        ("smart", "/static/icons/homeassistant.png"),
        ("iot", "/static/icons/homeassistant.png"),
        ("zigbee", "/static/icons/homeassistant.png"),
        ("domoticz", "/static/icons/homeassistant.png"),
        ("academy", "/static/icons/academy.png"),
        ("moodle", "/static/icons/academy.png"),
        ("canvas", "/static/icons/academy.png"),
        ("school", "/static/icons/academy.png"),
        ("learn", "/static/icons/academy.png"),
        ("course", "/static/icons/academy.png"),
        ("education", "/static/icons/academy.png"),
        ("meeting", "/static/icons/meetings.png"),
        ("jitsi", "/static/icons/meetings.png"),
        ("conference", "/static/icons/meetings.png"),
        ("videocall", "/static/icons/meetings.png"),
        ("zoom", "/static/icons/zoom.png"),
        ("searx", "/static/icons/duckduckgo.png"),
        ("whoogle", "/static/icons/duckduckgo.png"),
        ("duckduckgo", "/static/icons/duckduckgo.png"),
        ("search", "/static/icons/duckduckgo.png"),
        ("esxi", "/static/icons/esxi.png"),
        ("vmware", "/static/icons/esxi.png"),
        ("vsphere", "/static/icons/esxi.png"),
        ("vcenter", "/static/icons/esxi.png"),
        ("cockpit", "/static/icons/cockpit.png"),
        ("casaos", "/static/icons/casaos.png")
    ]

    for term, icon_url in semantic_map:
        if term in c_low:
            return icon_url

    return "/static/icons/casaos.png"

def get_host_lan_ip(client_host=None):
    """Detect the host machine's primary local IP address without returning internal Docker IPs."""
    # 1. If a valid client host was provided from the HTTP request, trust it
    if client_host and client_host.strip() and client_host not in ("127.0.0.1", "localhost", "0.0.0.0", "::1"):
        ch = client_host.strip()
        # Ensure it's not a container bridge IP
        if not re.match(r'^172\.(1[6-9]|2[0-9]|3[0-1])\.', ch):
            return ch

    # 2. Check host routing tables (/host/proc or /proc) for physical LAN IPs (192.168.x.x or 10.x.x.x)
    for fib_path in ("/host/proc/net/fib_trie", "/proc/net/fib_trie"):
        if os.path.exists(fib_path):
            try:
                with open(fib_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                matches = re.findall(r'(\d+\.\d+\.\d+\.\d+)\s*\n\s*/32 host LOCAL', content)
                for candidate in matches:
                    if candidate.startswith("127.") or candidate.startswith("100.") or candidate.startswith("169.254."):
                        continue
                    # Skip Docker bridge networks (172.16.0.0/12)
                    if re.match(r'^172\.(1[6-9]|2[0-9]|3[0-1])\.', candidate):
                        continue
                    return candidate
            except Exception:
                pass

    # 3. Socket connect probe
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(('1.1.1.1', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.') and not re.match(r'^172\.(1[6-9]|2[0-9]|3[0-1])\.', ip):
            return ip
    except Exception:
        pass

    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith('127.') and not re.match(r'^172\.(1[6-9]|2[0-9]|3[0-1])\.', ip):
            return ip
    except Exception:
        pass

    # 4. Fallback: if client_host is available, use it
    if client_host and client_host.strip() and client_host not in ("0.0.0.0", "::1"):
        return client_host.strip()

    return "127.0.0.1"

def get_tailscale_info():
    """Detect Tailscale DNS Name and IP."""
    ts_domain = os.environ.get("TAILSCALE_DOMAIN", "")
    ts_ip = os.environ.get("TAILSCALE_IP", "")
    try:
        res = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=1.5)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            if not ts_domain:
                ts_domain = data.get("Self", {}).get("DNSName", "").rstrip(".")
            if not ts_ip:
                ips = data.get("Self", {}).get("TailscaleIPs", [])
                if ips:
                    ts_ip = ips[0]
    except Exception:
        pass
    return ts_domain, ts_ip

def detect_docker_applications(client_host=None):
    """
    Inspect running Docker containers on the host, parse published host ports,
    match them to known homelab applications, and return structured card proposals.
    """
    docker_installed = True
    try:
        cmd = ["docker", "ps", "-a", "--format", '{{.Names}}|{{.Status}}|{{.Ports}}|{{.Image}}|{{.Label "com.docker.compose.project"}}']
        dps = subprocess.check_output(cmd, timeout=4).decode("utf-8", errors="ignore")
    except Exception as e:
        return {
            "status": "docker_unavailable",
            "docker_installed": False,
            "error": str(e),
            "apps": []
        }

    settings = get_settings()
    lan_ip = settings.get("lan_host") or get_host_lan_ip(client_host=client_host)
    ts_domain = settings.get("tailscale_domain") or get_tailscale_info()[0]

    # Load existing cards to prevent duplicates
    existing_cards = get_cards()
    existing_urls = {c.get("lan_url", "").strip().rstrip('/') for c in existing_cards if c.get("lan_url")}
    existing_names = {c.get("name", "").strip().lower() for c in existing_cards if c.get("name")}

    detected = []
    seen_ports = set()

    for line in dps.splitlines():
        if not line.strip() or "|" not in line:
            continue
        parts = line.split("|")
        c_name = parts[0].strip()
        c_stat = parts[1].strip()
        c_ports = parts[2].strip() if len(parts) > 2 else ""
        c_img = parts[3].strip() if len(parts) > 3 else ""
        c_proj = parts[4].strip() if len(parts) > 4 else ""

        c_low = (c_name + " " + c_img).lower()

        # Match any published host port mappings:
        # e.g. 0.0.0.0:8080->80/tcp, 192.168.1.5:8080->80/tcp, [::]:8080->80/tcp
        port_matches = re.findall(r'(?:[0-9a-fA-F\.:\[\]]+):(\d+)->(\d+)', c_ports)

        chosen_host_port = None
        if port_matches:
            chosen_host_port = port_matches[0][0]
            for host_p, cont_p in port_matches:
                if cont_p in ("80", "443", "8080", "3000", "8090", "2283", "4533", "8384", "9000", "5000", "8000", "8095"):
                    chosen_host_port = host_p
                    break
        else:
            # Fallback 1: check exposed ports like 80/tcp or 8080/tcp
            exposed_matches = re.findall(r'(\d+)/(?:tcp|udp)', c_ports)
            if exposed_matches:
                for exp_p in exposed_matches:
                    if exp_p in ("80", "443", "8080", "3000", "8090", "2283", "4533", "8384", "9000", "5000", "8000"):
                        chosen_host_port = exp_p
                        break
                if not chosen_host_port:
                    chosen_host_port = exposed_matches[0]

        # Fallback 2: check known applications for host-network or unmapped containers
        if not chosen_host_port:
            for k, meta in KNOWN_APP_DEFINITIONS.items():
                if k in c_low:
                    port_hint = re.search(r':(\d+)', meta.get("subtitle", "") + " " + meta.get("second_lan_url", ""))
                    if port_hint:
                        chosen_host_port = port_hint.group(1)
                    break

        if not chosen_host_port:
            continue

        # Skip database / worker containers only if they don't expose a user web portal
        if any(skip in c_low for skip in ("redis", "postgres", "database", "pgvector", "mariadb", "mysql", "machine_learning", "notify-push", "fulltextsearch", "clamav", "imaginary", "whiteboard", "eurooffice", "watchtower", "borgbackup")):
            if "mastercontainer" not in c_low and chosen_host_port in ("5432", "6379", "9200", "9300"):
                continue

        if chosen_host_port in seen_ports:
            continue
        seen_ports.add(chosen_host_port)

        proto = "https" if chosen_host_port in ("443", "8443", "9443", "8080") and ("aio" in c_low or "ssl" in c_low) else "http"
        lan_url = f"{proto}://{lan_ip}:{chosen_host_port}"
        ts_url = f"{proto}://{ts_domain}:{chosen_host_port}" if ts_domain else ""

        # App Identity Matching
        app_key = None
        for key in KNOWN_APP_DEFINITIONS.keys():
            if key in c_low:
                app_key = key
                break

        second_link_name = ""
        second_lan_url = ""
        second_ts_url = ""

        if app_key:
            meta = KNOWN_APP_DEFINITIONS[app_key]
            app_name = meta["name"]
            subtitle = meta["subtitle"]
            category = meta["category"]
            icon = meta["icon"]
            if meta.get("second_link_name"):
                second_link_name = meta.get("second_link_name")
        else:
            cleaned = re.sub(r'[-_](?:app|main|server|core|web)?[-_]?\d+$', '', c_name)
            words = [w.capitalize() for w in re.split(r'[-_]', cleaned) if w]
            app_name = " ".join(words) if words else c_name
            subtitle = f"Self-Hosted {app_name} Web App"
            category = "Cloud & Office"
            icon = resolve_app_icon(c_name, c_img)

        if "nextcloud" in (app_name.lower() + " " + c_name.lower()):
            second_link_name = "Admin"
            second_lan_url = f"https://{lan_ip}:8080"
            second_ts_url = f"https://{ts_domain}:8080" if ts_domain else ""

        is_added = (lan_url.rstrip('/') in existing_urls) or (app_name.lower() in existing_names)

        detected.append({
            "container_name": c_name,
            "name": app_name,
            "subtitle": subtitle,
            "category": category,
            "icon": icon,
            "port": chosen_host_port,
            "lan_url": lan_url,
            "ts_url": ts_url,
            "second_link_name": second_link_name,
            "second_lan_url": second_lan_url,
            "second_ts_url": second_ts_url,
            "status": "running" if "Up" in c_stat else "stopped",
            "is_already_added": is_added
        })

    # Sort so unadded items come first
    detected.sort(key=lambda x: (x["is_already_added"], x["name"]))

    return {
        "status": "success",
        "docker_installed": docker_installed,
        "lan_ip": lan_ip,
        "ts_domain": ts_domain,
        "total_detected": len(detected),
        "unadded_count": sum(1 for a in detected if not a["is_already_added"]),
        "apps": detected
    }

def batch_add_cards(cards_data, replace_existing=False):
    """
    Batch add or sync/fix application cards in cards.json.
    - If replace_existing is True (e.g. running Setup Wizard):
      Clears previous cards and populates ONLY the newly selected applications.
    - If replace_existing is False:
      Updates existing cards or creates new ones, preserving customized cards.
    """
    if not isinstance(cards_data, list):
        return {"status": "error", "message": "cards_data must be a list"}

    if replace_existing:
        current_cards = []
        current_max_order = 0
    else:
        current_cards = get_cards()
        current_max_order = max([c.get("order", 0) for c in current_cards], default=0)

    created_count = 0
    updated_count = 0

    app_keywords = (
        "musicgrabber", "navidrome", "immich", "nextcloud", "docuseal",
        "stirling", "papra", "portainer", "syncthing", "homeassistant",
        "spiderscan", "cockpit", "casaos", "vaultwarden", "uptime", "jellyfin", "plex", "ollama"
    )

    for item in cards_data:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "").strip() or "Unnamed App"
        lan_url = item.get("lan_url", "").strip()
        ts_url = item.get("ts_url", "").strip()
        second_link_name = item.get("second_link_name", "").strip()
        second_lan_url = item.get("second_lan_url", "").strip()
        second_ts_url = item.get("second_ts_url", "").strip()
        category = item.get("category", "Apps").strip() or "Apps"
        subtitle = item.get("subtitle", "").strip()
        container_name = item.get("container_name", "").strip().lower()
        port = str(item.get("port", "")).strip()
        icon = item.get("icon", "").strip()
        if not icon or (icon in ("/static/icons/portainer.png", "/static/icons/cockpit.png", "/static/icons/casaos.png") and "portainer" not in (name + " " + container_name).lower()):
            resolved = resolve_app_icon(container_name or name, "")
            if resolved and resolved != "/static/icons/casaos.png":
                icon = resolved
            elif not icon:
                icon = resolved or "/static/icons/portainer.png"

        matched_card = None
        for c in current_cards:
            c_name = c.get("name", "").strip().lower()
            c_id = c.get("id", "").strip().lower()
            c_lan = c.get("lan_url", "").strip().lower().rstrip('/')
            c_ts = c.get("ts_url", "").strip().lower().rstrip('/')

            # 1. Match by known app keyword
            matched_kw = False
            for kw in app_keywords:
                if (kw in container_name or kw in name.lower()):
                    if kw in c_name or kw in c_id or kw in c_lan or kw in c_ts:
                        matched_card = c
                        matched_kw = True
                        break
            if matched_kw:
                break

            # 2. Match by exact or substring name
            if name.lower() == c_name or (len(name) > 4 and (name.lower() in c_name or c_name in name.lower())):
                matched_card = c
                break

            # 3. Match by published port
            if port and (f":{port}" in c_lan or f":{port}" in c_ts):
                matched_card = c
                break

            # 4. Match by exact LAN URL
            if lan_url and lan_url.rstrip('/') == c_lan:
                matched_card = c
                break

        if matched_card:
            # Fix and update existing card configuration
            matched_card["name"] = name
            if subtitle:
                matched_card["subtitle"] = subtitle
            # Only update lan_url if the existing card didn't already have an external domain configured by user
            existing_lan = matched_card.get("lan_url", "")
            if not existing_lan or ("192.168" in existing_lan or "127.0.0.1" in existing_lan or ":8080" in existing_lan):
                if lan_url:
                    matched_card["lan_url"] = lan_url
            if ts_url and not matched_card.get("ts_url"):
                matched_card["ts_url"] = ts_url
            if icon:
                matched_card["icon"] = icon
            elif matched_card.get("icon") in ("/static/icons/portainer.png", "/static/icons/cockpit.png", "/static/icons/casaos.png") and "portainer" not in matched_card.get("name", "").lower():
                resolved = resolve_app_icon(matched_card.get("name", ""), "")
                if resolved:
                    matched_card["icon"] = resolved
            if category:
                matched_card["category"] = category
            if second_link_name:
                matched_card["second_link_name"] = second_link_name
            if second_lan_url:
                matched_card["second_lan_url"] = second_lan_url
            if second_ts_url:
                matched_card["second_ts_url"] = second_ts_url
            updated_count += 1
        else:
            # Create new card
            current_max_order += 1
            new_card = {
                "id": "card_" + uuid.uuid4().hex[:8],
                "name": name,
                "subtitle": subtitle,
                "lan_url": lan_url,
                "ts_url": ts_url,
                "second_link_name": second_link_name,
                "second_lan_url": second_lan_url,
                "second_ts_url": second_ts_url,
                "icon": icon,
                "category": category,
                "order": current_max_order
            }
            current_cards.append(new_card)
            created_count += 1

    save_cards(current_cards)

    return {
        "status": "success",
        "created_count": created_count,
        "updated_count": updated_count,
        "total_affected": created_count + updated_count,
        "total_cards": len(current_cards)
    }
