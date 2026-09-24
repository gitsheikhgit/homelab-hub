#!/usr/bin/env python3
"""
Backup & Migration Manager for Homelab Hub
Exports and imports complete system configuration packages:
- settings.json (dashboard preferences, layout, widgets, themes, icon sizes)
- cards.json (application cards, URLs, custom categories, badges)
- tasks.json (scheduled maintenance & automation tasks)
- calendar_events.json (energy records & event history)
- data/uploads/ (custom user-uploaded icons and wallpapers, base64 bundled)
- system_fingerprint (hardware drives, host identity, docker images for new system verification)
"""

import os
import json
import base64
import platform
import subprocess
import psutil
from datetime import datetime
from card_manager import (
    BASE_DIR,
    DATA_DIR,
    CARDS_FILE,
    SETTINGS_FILE,
    UPLOAD_DIR,
    UPLOAD_ICONS_DIR,
    UPLOAD_WALLPAPERS_DIR,
    get_cards,
    get_settings,
    save_cards,
    save_settings,
    atomic_save_json
)

TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
CALENDAR_EVENTS_FILE = os.path.join(DATA_DIR, "calendar_events.json")

def get_system_fingerprint():
    """Captures host identity, mounted drives, and installed Docker images/containers."""
    hostname = platform.node() or "homelab-server"
    
    # 1. Capture Mounted Storage Drives
    drives = []
    try:
        seen_mounts = set()
        for p in psutil.disk_partitions(all=False):
            mp = p.mountpoint
            if mp.startswith(("/var/lib/docker", "/boot", "/etc", "/var/log")):
                continue
            if mp in seen_mounts:
                continue
            seen_mounts.add(mp)
            total_gb = 0
            try:
                usage = psutil.disk_usage(mp)
                total_gb = round(usage.total / (1024 ** 3), 1)
            except Exception:
                pass
            drives.append({
                "mountpoint": mp,
                "device": p.device,
                "fstype": p.fstype,
                "total_gb": total_gb
            })
    except Exception as e:
        print(f"Error reading disk partitions: {e}")

    # 2. Capture Docker Images & Containers
    docker_images = []
    docker_containers = []
    try:
        raw_imgs = subprocess.check_output(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            stderr=subprocess.DEVNULL,
            timeout=6
        ).decode("utf-8", errors="ignore").splitlines()
        docker_images = sorted(list(set(img.strip() for img in raw_imgs if img.strip() and not img.startswith("<none>"))))
    except Exception:
        pass

    try:
        raw_conts = subprocess.check_output(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            stderr=subprocess.DEVNULL,
            timeout=6
        ).decode("utf-8", errors="ignore").splitlines()
        docker_containers = sorted(list(set(c.strip() for c in raw_conts if c.strip())))
    except Exception:
        pass

    return {
        "hostname": hostname,
        "drives": drives,
        "docker": {
            "images": docker_images,
            "containers": docker_containers
        }
    }

def encode_directory_files(directory_path, max_file_size_mb=12):
    """Encodes files in a directory as base64 data URIs."""
    encoded = {}
    if not os.path.exists(directory_path):
        return encoded

    for fname in os.listdir(directory_path):
        if fname.startswith(".") or fname == ".gitkeep":
            continue
        fpath = os.path.join(directory_path, fname)
        if os.path.isfile(fpath):
            try:
                size_mb = os.path.getsize(fpath) / (1024 * 1024)
                if size_mb > max_file_size_mb:
                    continue
                with open(fpath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                    # Determine MIME type
                    ext = os.path.splitext(fname)[1].lower().lstrip(".")
                    mime = "image/png"
                    if ext in ("jpg", "jpeg"):
                        mime = "image/jpeg"
                    elif ext == "svg":
                        mime = "image/svg+xml"
                    elif ext == "webp":
                        mime = "image/webp"
                    elif ext == "gif":
                        mime = "image/gif"
                    encoded[fname] = f"data:{mime};base64,{b64}"
            except Exception as e:
                print(f"Error encoding {fpath}: {e}")
    return encoded

def generate_backup_package():
    """Generates complete standalone JSON backup package."""
    # 1. Settings, Cards, Tasks
    settings = get_settings()
    cards = get_cards()
    
    tasks = []
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except Exception:
            pass

    calendar_events = []
    if os.path.exists(CALENDAR_EVENTS_FILE):
        try:
            with open(CALENDAR_EVENTS_FILE, "r", encoding="utf-8") as f:
                calendar_events = json.load(f)
        except Exception:
            pass

    # 2. Uploaded Custom Icons and Wallpapers
    icons_b64 = encode_directory_files(UPLOAD_ICONS_DIR, max_file_size_mb=4)
    wallpapers_b64 = encode_directory_files(UPLOAD_WALLPAPERS_DIR, max_file_size_mb=15)

    # 3. System Fingerprint
    fingerprint = get_system_fingerprint()

    package = {
        "format": "homelab_hub_backup",
        "version": "1.1.2",
        "created_at": datetime.now().isoformat(),
        "system_fingerprint": fingerprint,
        "settings": settings,
        "cards": cards,
        "tasks": tasks,
        "calendar_events": calendar_events,
        "uploads": {
            "icons": icons_b64,
            "wallpapers": wallpapers_b64
        }
    }
    return package

def inspect_backup_package(backup_dict):
    """
    Analyzes an uploaded backup package and compares it with the current running system.
    Identifies machine differences, missing storage drives, and missing Docker images.
    """
    if not isinstance(backup_dict, dict) or backup_dict.get("format") != "homelab_hub_backup":
        return {
            "status": "error",
            "message": "Invalid backup file. File must be a valid Homelab Hub backup (.json)."
        }

    current_fingerprint = get_system_fingerprint()
    backup_fingerprint = backup_dict.get("system_fingerprint", {})

    backup_host = backup_fingerprint.get("hostname", "Unknown")
    current_host = current_fingerprint.get("hostname", "Unknown")
    is_same_host = (backup_host.strip().lower() == current_host.strip().lower())

    warnings = []
    if not is_same_host:
        warnings.append({
            "type": "new_machine",
            "title": "Restoring to a Different Machine",
            "message": f"This backup was generated on host '{backup_host}', but your current system is '{current_host}'. Homelab Hub has verified your drives and Docker fleet below."
        })

    # 1. Drive Verification
    current_mounts = set(d["mountpoint"] for d in current_fingerprint.get("drives", []))
    backup_drives = backup_fingerprint.get("drives", [])
    
    matched_drives = []
    missing_drives = []
    for d in backup_drives:
        mp = d.get("mountpoint") if isinstance(d, dict) else str(d)
        if mp in current_mounts:
            matched_drives.append(d)
        else:
            missing_drives.append(d)

    if missing_drives:
        missing_paths = [d.get("mountpoint", "") for d in missing_drives]
        warnings.append({
            "type": "missing_drives",
            "title": "Storage Drives / Mounts Missing",
            "message": f"{len(missing_drives)} storage path(s) in the backup were not found on this machine: {', '.join(missing_paths)}. Any card or storage widget pointing to these paths may need to be remounted or updated."
        })

    # 2. Docker Images Verification
    current_images = set(current_fingerprint.get("docker", {}).get("images", []))
    backup_images = backup_fingerprint.get("docker", {}).get("images", [])
    
    # Also collect any image references declared in backup cards
    for card in backup_dict.get("cards", []):
        img = card.get("docker_image") or card.get("image")
        if img and img not in backup_images:
            backup_images.append(img)

    matched_images = []
    missing_images = []
    for img in backup_images:
        # Check direct match or repository prefix match
        img_name = img.split(":")[0] if ":" in img else img
        has_match = any(img == cur or cur.startswith(img_name + ":") for cur in current_images)
        if has_match:
            matched_images.append(img)
        else:
            missing_images.append(img)

    # Docker Containers Verification
    current_containers = set(current_fingerprint.get("docker", {}).get("containers", []))
    backup_containers = backup_fingerprint.get("docker", {}).get("containers", [])
    missing_containers = [c for c in backup_containers if c not in current_containers]

    if missing_images:
        warnings.append({
            "type": "missing_docker_images",
            "title": "Docker Containers Not Installed",
            "message": f"{len(missing_images)} Docker image(s) from your previous system are not yet installed on this server. Your app cards will still be restored, but containers may need to be pulled/started."
        })

    # 3. Content Summary
    cards = backup_dict.get("cards", [])
    settings = backup_dict.get("settings", {})
    tasks = backup_dict.get("tasks", [])
    uploads = backup_dict.get("uploads", {})
    icons_count = len(uploads.get("icons", {}))
    wallpapers_count = len(uploads.get("wallpapers", {}))

    return {
        "status": "success",
        "is_same_system": is_same_host,
        "warnings": warnings,
        "backup_metadata": {
            "created_at": backup_dict.get("created_at"),
            "version": backup_dict.get("version", "1.0.0"),
            "backup_hostname": backup_host,
            "current_hostname": current_host
        },
        "drives_check": {
            "matched": matched_drives,
            "missing": missing_drives,
            "total_backup_drives": len(backup_drives),
            "current_drives_count": len(current_fingerprint.get("drives", []))
        },
        "docker_check": {
            "matched_images": matched_images,
            "missing_images": missing_images,
            "missing_containers": missing_containers,
            "total_backup_images": len(backup_images)
        },
        "summary": {
            "cards_count": len(cards),
            "tasks_count": len(tasks),
            "custom_icons_count": icons_count,
            "custom_wallpapers_count": wallpapers_count,
            "theme": settings.get("theme", "dark"),
            "quick_icon_size_px": settings.get("quick_icon_size_px", 34)
        }
    }

def restore_backup_package(backup_dict, preserve_lan_host=True):
    """
    Restores settings, cards, tasks, and media assets from a backup dictionary.
    """
    if not isinstance(backup_dict, dict) or backup_dict.get("format") != "homelab_hub_backup":
        return {"status": "error", "message": "Invalid backup package format."}

    # 1. Restore Custom Media Assets (Icons & Wallpapers)
    uploads = backup_dict.get("uploads", {})
    restored_icons = 0
    restored_wallpapers = 0

    icons_data = uploads.get("icons", {})
    for fname, data_uri in icons_data.items():
        try:
            if "," in data_uri:
                b64 = data_uri.split(",", 1)[1]
            else:
                b64 = data_uri
            fbytes = base64.b64decode(b64)
            dest = os.path.join(UPLOAD_ICONS_DIR, fname)
            with open(dest, "wb") as f:
                f.write(fbytes)
            restored_icons += 1
        except Exception as e:
            print(f"Error restoring icon {fname}: {e}")

    wallpapers_data = uploads.get("wallpapers", {})
    for fname, data_uri in wallpapers_data.items():
        try:
            if "," in data_uri:
                b64 = data_uri.split(",", 1)[1]
            else:
                b64 = data_uri
            fbytes = base64.b64decode(b64)
            dest = os.path.join(UPLOAD_WALLPAPERS_DIR, fname)
            with open(dest, "wb") as f:
                f.write(fbytes)
            restored_wallpapers += 1
        except Exception as e:
            print(f"Error restoring wallpaper {fname}: {e}")

    # 2. Restore Cards
    cards = backup_dict.get("cards")
    if isinstance(cards, list):
        save_cards(cards)

    # 3. Restore Tasks
    tasks = backup_dict.get("tasks")
    if isinstance(tasks, list):
        atomic_save_json(TASKS_FILE, tasks)

    # 4. Restore Calendar Events (if present)
    calendar_events = backup_dict.get("calendar_events")
    if isinstance(calendar_events, list) and calendar_events:
        atomic_save_json(CALENDAR_EVENTS_FILE, calendar_events)

    # 5. Restore Settings
    settings = backup_dict.get("settings")
    if isinstance(settings, dict):
        current_settings = get_settings()
        if preserve_lan_host and current_settings.get("lan_host"):
            # Keep current host IP if already configured
            settings["lan_host"] = current_settings["lan_host"]
        save_settings(settings)

    return {
        "status": "success",
        "message": "Dashboard settings, cards, automations, and media successfully restored!",
        "restored": {
            "cards": len(cards) if isinstance(cards, list) else 0,
            "tasks": len(tasks) if isinstance(tasks, list) else 0,
            "icons": restored_icons,
            "wallpapers": restored_wallpapers
        }
    }
