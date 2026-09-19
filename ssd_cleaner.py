#!/usr/bin/env python3
"""
SSD Garbage Collector & Storage Optimizer
Itemized, safe scanner and selective purger for main OS SSD (/dev/sda2).
"""

import os
import re
import json
import glob
import shutil
import psutil
import subprocess
from datetime import datetime

def format_bytes(size_bytes):
    if size_bytes <= 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit in ['MB', 'GB', 'TB'] else f"{int(size_bytes)} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

def get_ssd_usage():
    try:
        usage = psutil.disk_usage('/')
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round(usage.used / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "percent": usage.percent
        }
    except Exception as e:
        return {"error": str(e)}

def get_container_info():
    """Returns active containers, their images, IDs, and names."""
    try:
        cid_list = subprocess.check_output(['docker', 'ps', '-aq'], stderr=subprocess.DEVNULL, timeout=5).decode().split()
        if not cid_list:
            return [], set(), set()
        c_info = json.loads(subprocess.check_output(['docker', 'inspect'] + cid_list, stderr=subprocess.DEVNULL, timeout=10).decode())
        
        used_image_ids = set()
        used_image_names = set()
        containers = []
        
        for c in c_info:
            cid = c.get('Id', '')
            cname = c.get('Name', '').lstrip('/')
            img_id = c.get('Image', '')
            cfg_img = c.get('Config', {}).get('Image', '')
            status = c.get('State', {}).get('Status', 'unknown')
            
            used_image_ids.add(img_id)
            if cfg_img:
                used_image_names.add(cfg_img)
                # also add without tag or with :latest
                if ':' in cfg_img:
                    used_image_names.add(cfg_img.split(':')[0])
                else:
                    used_image_names.add(f"{cfg_img}:latest")
            
            containers.append({
                "id": cid[:12],
                "full_id": cid,
                "name": cname,
                "image": cfg_img,
                "image_id": img_id,
                "status": status,
                "is_running": status == "running"
            })
            
        return containers, used_image_ids, used_image_names
    except Exception:
        return [], set(), set()

def scan_unused_images(containers, used_image_ids, used_image_names):
    """Scan all Docker images and itemize unused ones."""
    items = []
    try:
        img_id_list = subprocess.check_output(['docker', 'images', '-q'], stderr=subprocess.DEVNULL, timeout=5).decode().split()
        if not img_id_list:
            return items
        
        # Deduplicate IDs
        unique_ids = list(dict.fromkeys(img_id_list))
        img_info = json.loads(subprocess.check_output(['docker', 'image', 'inspect'] + unique_ids, stderr=subprocess.DEVNULL, timeout=10).decode())
        
        for img in img_info:
            iid = img.get('Id', '')
            short_id = iid.replace('sha256:', '')[:12]
            tags = img.get('RepoTags', [])
            size = img.get('Size', 0)
            created = img.get('Created', '')[:10]
            
            # Check if this image or any of its tags are in use
            is_used = (iid in used_image_ids)
            if not is_used:
                for t in tags:
                    if t in used_image_names:
                        is_used = True
                        break
                    repo = t.split(':')[0] if ':' in t else t
                    if repo in used_image_names:
                        is_used = True
                        break
            
            tag_display = ', '.join(tags) if tags else '<untagged/dangling>'
            repo_name = tags[0] if tags else short_id
            
            if not is_used:
                items.append({
                    "key": f"image:{iid}",
                    "id": short_id,
                    "full_id": iid,
                    "name": tag_display,
                    "repo": repo_name,
                    "tags": tags,
                    "size_bytes": size,
                    "size_formatted": format_bytes(size),
                    "created": created,
                    "is_used": False,
                    "risk": "safe_unused",
                    "risk_label": "Safe · Unused by any container",
                    "description": "Downloaded image not referenced by any running or stopped container",
                    "what_is_being_cleaned": f"Docker Image: {repo_name} ({short_id}). Confirmed: 0 active containers depend on it.",
                    "default_selected": True
                })
    except Exception:
        pass
    
    return items

def scan_container_logs(containers):
    """Scan oversized container logs (>5MB) itemized per container."""
    items = []
    try:
        c_map = {c['full_id']: c['name'] for c in containers}
        cmd = ["sudo", "find", "/var/lib/docker/containers/", "-name", "*-json.log", "-size", "+5M"]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10).decode("utf-8", errors="ignore").strip()
        
        if out:
            for logpath in out.splitlines():
                try:
                    s_out = subprocess.check_output(["sudo", "stat", "-c", "%s", logpath], timeout=5).decode().strip()
                    size = int(s_out)
                    cid = os.path.basename(os.path.dirname(logpath))
                    cname = c_map.get(cid, cid[:12])
                    
                    items.append({
                        "key": f"log:{cname}:{logpath}",
                        "id": cid[:12],
                        "name": f"{cname} Log",
                        "container_name": cname,
                        "path": logpath,
                        "size_bytes": size,
                        "size_formatted": format_bytes(size),
                        "risk": "safe_truncate",
                        "risk_label": "Safe · Zero Downtime",
                        "description": "Empties log to 0 bytes without stopping container or breaking Docker logging",
                        "what_is_being_cleaned": f"Log File: {logpath} ({format_bytes(size)}). Truncated safely live; container stays running.",
                        "default_selected": True
                    })
                except Exception:
                    pass
    except Exception:
        pass
    
    # Sort largest logs first
    items.sort(key=lambda x: x["size_bytes"], reverse=True)
    return items

def scan_stopped_containers(containers):
    """Itemize stopped containers (protecting Nextcloud AIO background workers)."""
    items = []
    for c in containers:
        if not c["is_running"]:
            cname = c["name"]
            is_aio_worker = cname.startswith("nextcloud-aio-")
            items.append({
                "key": f"container:{c['full_id']}",
                "id": c["id"],
                "full_id": c["full_id"],
                "name": cname,
                "image": c["image"],
                "status": c["status"],
                "is_protected": is_aio_worker,
                "size_bytes": 0,
                "size_formatted": "Metadata",
                "risk": "protected" if is_aio_worker else "caution",
                "risk_label": "Protected (AIO Worker)" if is_aio_worker else "Optional · Exited Container",
                "description": "Nextcloud AIO automated worker (Protected from deletion)" if is_aio_worker else f"Exited container ({c['image']})",
                "what_is_being_cleaned": f"Container Instance: {cname} [{c['image']}]. Status: {c['status']}.",
                "default_selected": False
            })
    return items

def scan_system_garbage():
    """Itemize system logs, journals, caches, and builder artifacts."""
    items = []
    
    # 1. Systemd Journal Archives (>100MB)
    try:
        out = subprocess.check_output(["journalctl", "--disk-usage"], stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        m = re.search(r'take up\s+([\d\.]+)\s*([KMGTP]?B)', out)
        if m:
            val, unit = float(m.group(1)), m.group(2)
            multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
            current_bytes = int(val * multipliers.get(unit, 1))
            reclaimable = max(0, current_bytes - (100 * 1024 * 1024))
            if reclaimable > 0 or current_bytes > 0:
                items.append({
                    "key": "system:systemd_journal",
                    "id": "systemd_journal",
                    "name": "Systemd Journal Historical Archives",
                    "size_bytes": reclaimable,
                    "size_formatted": format_bytes(reclaimable) if reclaimable > 0 else f"{format_bytes(current_bytes)} (At 100MB limit)",
                    "risk": "safe",
                    "risk_label": "Safe · Retains 100MB",
                    "description": "Vacuums archived journal logs beyond the safe 100MB threshold",
                    "what_is_being_cleaned": f"Systemd Journals in /var/log/journal. Keeps last 100MB; reclaims {format_bytes(reclaimable)}.",
                    "default_selected": reclaimable > 10 * 1024 * 1024
                })
    except Exception:
        pass

    # 2. Rotated & Compressed Logs in /var/log
    try:
        patterns = [
            "/var/log/*.gz",
            "/var/log/*.[0-9]",
            "/var/log/*.old",
            "/var/log/apt/*.gz",
            "/var/log/unattended-upgrades/*.gz"
        ]
        log_bytes = 0
        log_count = 0
        for pat in patterns:
            for f in glob.glob(pat):
                try:
                    s = os.path.getsize(f)
                    log_bytes += s
                    log_count += 1
                except Exception:
                    pass
        if log_count > 0:
            items.append({
                "key": "system:rotated_logs",
                "id": "rotated_logs",
                "name": f"Rotated & Compressed Logs ({log_count} files)",
                "size_bytes": log_bytes,
                "size_formatted": format_bytes(log_bytes),
                "risk": "safe",
                "risk_label": "Safe · Zero Risk",
                "description": "Archived compressed logs (*.gz, *.1) in /var/log. Active log files remain untouched.",
                "what_is_being_cleaned": f"Compressed System Logs: {log_count} archived files (*.gz, *.1) in /var/log.",
                "default_selected": True
            })
    except Exception:
        pass

    # 3. Playwright Headless Browser Cache
    try:
        p_dir = os.path.expanduser("~/.cache/ms-playwright")
        p_bytes = 0
        if os.path.exists(p_dir):
            for root, dirs, files in os.walk(p_dir):
                for f in files:
                    try:
                        p_bytes += os.path.getsize(os.path.join(root, f))
                    except Exception:
                        pass
        if p_bytes > 0:
            items.append({
                "key": "system:playwright_cache",
                "id": "playwright_cache",
                "name": "Playwright Headless Browser Cache",
                "size_bytes": p_bytes,
                "size_formatted": format_bytes(p_bytes),
                "risk": "safe",
                "risk_label": "Safe · Auto-recreated if needed",
                "description": "Old Chromium headless binaries in ~/.cache/ms-playwright",
                "what_is_being_cleaned": f"Browser Downloads: ~/.cache/ms-playwright ({format_bytes(p_bytes)}). Auto-redownloaded if ever needed.",
                "default_selected": True
            })
    except Exception:
        pass

    # 4. APT Package Cache
    try:
        cache_dir = "/var/cache/apt/archives"
        apt_bytes = 0
        apt_count = 0
        if os.path.exists(cache_dir):
            for f in os.listdir(cache_dir):
                if f.endswith(".deb"):
                    try:
                        apt_bytes += os.path.getsize(os.path.join(cache_dir, f))
                        apt_count += 1
                    except Exception:
                        pass
        if apt_count > 0:
            items.append({
                "key": "system:apt_cache",
                "id": "apt_cache",
                "name": f"APT Package Cache ({apt_count} packages)",
                "size_bytes": apt_bytes,
                "size_formatted": format_bytes(apt_bytes),
                "risk": "safe",
                "risk_label": "Safe · Zero Risk",
                "description": "Downloaded .deb archives in /var/cache/apt/archives from past updates",
                "what_is_being_cleaned": f"Debian Package Cache: {apt_count} cached .deb files in /var/cache/apt/archives.",
                "default_selected": True
            })
    except Exception:
        pass

    # 5. Docker Dangling & Build Cache
    try:
        df_out = subprocess.check_output(["docker", "system", "df", "--format", "{{json .}}"], stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        for row in df_out.splitlines():
            try:
                data = json.loads(row)
                if data.get("Type") == "Build Cache":
                    size_str = data.get("Size", "0B")
                    m = re.match(r'([\d\.]+)\s*([KMGTP]?B)', size_str)
                    if m and float(m.group(1)) > 0:
                        val, unit = float(m.group(1)), m.group(2)
                        multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
                        bc_bytes = int(val * multipliers.get(unit, 1))
                        items.append({
                            "key": "system:docker_build_cache",
                            "id": "docker_build_cache",
                            "name": "Docker Builder Cache",
                            "size_bytes": bc_bytes,
                            "size_formatted": format_bytes(bc_bytes),
                            "risk": "safe",
                            "risk_label": "Safe · Zero Risk",
                            "description": "Intermediate build stage layers and cache artifacts",
                            "what_is_being_cleaned": f"Build Cache: {format_bytes(bc_bytes)} of intermediate Docker build layers.",
                            "default_selected": True
                        })
            except Exception:
                pass
    except Exception:
        pass

    return items

def scan_all_garbage():
    """Run full diagnostic scan with complete itemization."""
    containers, used_image_ids, used_image_names = get_container_info()
    
    unused_images = scan_unused_images(containers, used_image_ids, used_image_names)
    container_logs = scan_container_logs(containers)
    system_garbage = scan_system_garbage()
    stopped_containers = scan_stopped_containers(containers)
    
    all_items = unused_images + container_logs + system_garbage + stopped_containers
    total_reclaimable = sum(i["size_bytes"] for i in (unused_images + container_logs + system_garbage))
    
    return {
        "timestamp": datetime.now().isoformat(),
        "ssd": get_ssd_usage(),
        "total_reclaimable_bytes": total_reclaimable,
        "total_reclaimable_formatted": format_bytes(total_reclaimable),
        "categories": all_items,
        "sections": {
            "unused_images": {
                "title": "Unused Downloaded Docker Images",
                "icon": "📦",
                "description": "Images sitting on disk that are NOT used by any running or stopped container. Safe to remove.",
                "items": unused_images
            },
            "container_logs": {
                "title": "Oversized Container Logs",
                "icon": "📜",
                "description": "Large active JSON logs (>5MB). Truncated safely to 0 bytes without downtime or stopping containers.",
                "items": container_logs
            },
            "system_garbage": {
                "title": "System Logs & Package Caches",
                "icon": "⚙️",
                "description": "Standard OS clutter: journal archives, old compressed logs, headless browser downloads, and APT cache.",
                "items": system_garbage
            },
            "stopped_containers": {
                "title": "Exited Non-Core Containers",
                "icon": "⏹️",
                "description": "Containers currently stopped. Note: Nextcloud AIO workers are permanently locked and protected.",
                "items": stopped_containers
            }
        }
    }

def clean_selected_items(selected_keys):
    """
    Safely purge selected items with strict runtime validations.
    Ensures active containers and Nextcloud AIO workers are never affected.
    """
    results = {}
    ssd_before = get_ssd_usage()
    containers, used_image_ids, used_image_names = get_container_info()
    
    for key in selected_keys:
        try:
            # 1. Image purge: "image:<sha256_id>"
            if key.startswith("image:"):
                img_id = key.split("image:", 1)[1]
                # SAFETY CHECK: Verify this image ID is NOT currently used by any container!
                if img_id in used_image_ids:
                    results[key] = {
                        "status": "skipped",
                        "message": "🛡️ Safety Lock: Image is actively attached to a container. Purge blocked."
                    }
                    continue
                
                # Delete image safely
                out = subprocess.check_output(["docker", "rmi", img_id], stderr=subprocess.STDOUT, timeout=30).decode("utf-8", errors="ignore").strip()
                results[key] = {"status": "success", "message": f"Purged image {img_id[:12]}"}

            # 2. Container log truncation: "log:<cname>:<logpath>"
            elif key.startswith("log:"):
                parts = key.split(":", 2)
                if len(parts) >= 3:
                    cname, logpath = parts[1], parts[2]
                    # Verify path is under /var/lib/docker/containers/ and ends with -json.log
                    if "/var/lib/docker/containers/" in logpath and logpath.endswith("-json.log"):
                        subprocess.run(["sudo", "truncate", "-s", "0", logpath], check=True, timeout=5)
                        results[key] = {"status": "success", "message": f"Truncated {cname} log to 0 bytes."}
                    else:
                        results[key] = {"status": "error", "message": "Invalid log path."}

            # 3. System actions
            elif key == "system:systemd_journal":
                out = subprocess.check_output(["sudo", "journalctl", "--vacuum-size=100M"], stderr=subprocess.STDOUT, timeout=20).decode().strip()
                results[key] = {"status": "success", "message": "Vacuumed systemd journal logs to 100MB threshold."}

            elif key == "system:rotated_logs":
                patterns = [
                    "/var/log/*.gz",
                    "/var/log/*.[0-9]",
                    "/var/log/*.old",
                    "/var/log/apt/*.gz",
                    "/var/log/unattended-upgrades/*.gz"
                ]
                removed = 0
                for pat in patterns:
                    for f in glob.glob(pat):
                        try:
                            subprocess.run(["sudo", "rm", "-f", f], timeout=5)
                            removed += 1
                        except Exception:
                            pass
                results[key] = {"status": "success", "message": f"Removed {removed} rotated/compressed log files."}

            elif key == "system:playwright_cache":
                p_dir = os.path.expanduser("~/.cache/ms-playwright")
                if os.path.exists(p_dir):
                    shutil.rmtree(p_dir, ignore_errors=True)
                results[key] = {"status": "success", "message": "Cleared ~/.cache/ms-playwright browser cache."}

            elif key == "system:apt_cache":
                subprocess.run(["sudo", "apt-get", "clean"], check=True, timeout=20)
                results[key] = {"status": "success", "message": "Purged APT package archives."}

            elif key == "system:docker_build_cache":
                subprocess.run(["docker", "builder", "prune", "-f"], check=True, timeout=20)
                results[key] = {"status": "success", "message": "Pruned Docker builder cache."}

            # 4. Container deletion: "container:<cid>"
            elif key.startswith("container:"):
                cid = key.split("container:", 1)[1]
                # SAFETY CHECK: Protect Nextcloud AIO workers
                c_match = [c for c in containers if c["full_id"] == cid or c["id"] == cid]
                if c_match:
                    target_c = c_match[0]
                    if target_c["name"].startswith("nextcloud-aio-"):
                        results[key] = {
                            "status": "skipped",
                            "message": f"🛡️ Protected: {target_c['name']} is a Nextcloud AIO service. Removal blocked."
                        }
                        continue
                    if target_c["is_running"]:
                        results[key] = {
                            "status": "skipped",
                            "message": f"🛡️ Safety Lock: {target_c['name']} is currently running. Stop it first if you wish to remove."
                        }
                        continue
                
                subprocess.run(["docker", "rm", cid], check=True, timeout=10)
                results[key] = {"status": "success", "message": f"Removed stopped container {cid[:12]}"}

        except Exception as e:
            results[key] = {"status": "error", "message": str(e)}

    ssd_after = get_ssd_usage()
    freed_bytes = max(0, ssd_before.get("used_bytes", 0) - ssd_after.get("used_bytes", 0))

    return {
        "status": "success",
        "ssd_before": ssd_before,
        "ssd_after": ssd_after,
        "freed_bytes": freed_bytes,
        "freed_formatted": format_bytes(freed_bytes),
        "results": results
    }

if __name__ == "__main__":
    import sys
    print("Testing itemized garbage scan...")
    res = scan_all_garbage()
    print(json.dumps(res, indent=2))
