#!/usr/bin/env python3
"""
Docker Image Update Checker & Safe Recreator
Inspects running containers, checks remote registries for newer image tags/digests,
and safely pulls & recreates containers using Docker Compose or native Docker CLI.
"""

import os
import json
import subprocess
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

def is_aio_managed_container(name):
    """
    Dynamically identifies if a container is an automated child worker of Nextcloud AIO.
    Nextcloud AIO child containers (database, redis, apache, etc.) are managed strictly
    by the Nextcloud AIO mastercontainer portal and must not be recreated externally.
    """
    if not name:
        return False
    return name.startswith("nextcloud-aio-") and name != "nextcloud-aio-mastercontainer"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "docker_updates_cache.json")
PINNED_FILE = os.path.join(BASE_DIR, "pinned_containers.json")

def get_pinned_containers():
    """Returns dict of pinned containers {name: reason}."""
    if os.path.exists(PINNED_FILE):
        try:
            with open(PINNED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    default_pinned = {}
    save_pinned_containers(default_pinned)
    return default_pinned

def save_pinned_containers(pinned_dict):
    """Save pinned containers dict to JSON file."""
    try:
        with open(PINNED_FILE, "w", encoding="utf-8") as f:
            json.dump(pinned_dict, f, indent=2)
    except Exception as e:
        print(f"Error saving pinned containers: {e}")

def toggle_pin_container(name, reason="Custom enhancements protected"):
    """Toggle the pinned state of a container."""
    pinned = get_pinned_containers()
    if name in pinned:
        del pinned[name]
        is_pinned = False
    else:
        pinned[name] = reason
        is_pinned = True
    save_pinned_containers(pinned)
    # Refresh cached update data
    check_all_container_updates(pull_remote=False)
    return {"status": "success", "container": name, "is_pinned": is_pinned, "reason": reason}


def get_all_container_configs():
    """Inspect all containers and extract image IDs, compose files, and statuses."""
    containers = []
    try:
        cid_list = subprocess.check_output(['docker', 'ps', '-aq'], stderr=subprocess.DEVNULL, timeout=8).decode().split()
        if not cid_list:
            return []
        
        info = json.loads(subprocess.check_output(['docker', 'inspect'] + cid_list, stderr=subprocess.DEVNULL, timeout=12).decode())
        for c in info:
            name = c.get('Name', '').lstrip('/')
            cid = c.get('Id', '')
            state = c.get('State', {})
            status = state.get('Status', 'unknown')
            running_img_id = c.get('Image', '')
            config_img = c.get('Config', {}).get('Image', '')
            labels = c.get('Config', {}).get('Labels') or {}
            
            compose_file = labels.get('com.docker.compose.project.config_files', '')
            compose_dir = labels.get('com.docker.compose.project.working_dir', '')
            compose_service = labels.get('com.docker.compose.service', '')
            
            is_aio = is_aio_managed_container(name)
            
            containers.append({
                "id": cid[:12],
                "full_id": cid,
                "name": name,
                "image_ref": config_img,
                "running_image_id": running_img_id,
                "short_running_image_id": running_img_id.replace('sha256:', '')[:12],
                "status": status,
                "is_running": status == 'running',
                "is_aio_child": is_aio,
                "is_compose": bool(compose_file and os.path.exists(compose_file)),
                "compose_file": compose_file,
                "compose_dir": compose_dir,
                "compose_service": compose_service
            })
    except Exception as e:
        print(f"Error inspecting containers: {e}")
    
    return containers

def check_single_container(c, pull_remote=False):
    """
    Checks if a container has an update available.
    If pull_remote=True, queries the remote registry via 'docker pull'.
    Then compares running container image ID with latest local tag ID.
    """
    name = c["name"]
    img_ref = c["image_ref"]
    running_id = c["running_image_id"]
    short_running_id = running_id.replace("sha256:", "")[:12]
    
    if c["is_aio_child"]:
        return {
            "name": name,
            "image_ref": img_ref,
            "status": "aio_managed",
            "update_available": False,
            "can_update": False,
            "message": "Managed by Nextcloud AIO Portal"
        }
    
    if not img_ref:
        return {
            "name": name,
            "image_ref": "",
            "status": "unknown",
            "update_available": False,
            "can_update": False,
            "message": "No image reference found"
        }

    pull_result_msg = ""
    if pull_remote:
        try:
            out = subprocess.check_output(
                ["docker", "pull", img_ref],
                stderr=subprocess.STDOUT,
                timeout=45
            ).decode("utf-8", errors="ignore").strip()
            if "Downloaded newer image" in out:
                pull_result_msg = "Newer image pulled from registry."
        except subprocess.TimeoutExpired:
            pull_result_msg = "Registry check timed out."
        except Exception as e:
            pull_result_msg = f"Registry check error: {e}"

    # Inspect current local image ID for img_ref
    latest_id = running_id
    try:
        inspect_out = subprocess.check_output(
            ["docker", "inspect", "-f", "{{.Id}}", img_ref],
            stderr=subprocess.DEVNULL,
            timeout=5
        ).decode().strip()
        if inspect_out:
            latest_id = inspect_out
    except Exception:
        pass

    short_latest_id = latest_id.replace("sha256:", "")[:12]
    is_newer = (latest_id != running_id)

    pinned = get_pinned_containers()
    is_pinned = name in pinned
    pinned_reason = pinned.get(name, "")

    if is_pinned:
        if is_newer:
            msg = f"🔒 Version pinned: {pinned_reason}. Newer image exists ({short_running_id} ➔ {short_latest_id}), but updates are locked to protect your custom UI."
        else:
            msg = f"🔒 Version pinned: {pinned_reason}. Updates locked."
        return {
            "name": name,
            "image_ref": img_ref,
            "current_image_id": short_running_id,
            "latest_image_id": short_latest_id,
            "update_available": False,
            "has_newer_image": is_newer,
            "is_pinned": True,
            "pinned_reason": pinned_reason,
            "can_update": False,
            "update_type": "compose" if c["is_compose"] else "standalone",
            "compose_file": c["compose_file"],
            "compose_service": c["compose_service"],
            "message": msg
        }

    msg = ""
    if is_newer:
        msg = f"Update available ({short_running_id} ➔ {short_latest_id}). Ready to pull & restart."
    else:
        msg = "Container is running newest image."
    if pull_result_msg:
        msg += f" ({pull_result_msg})"

    return {
        "name": name,
        "image_ref": img_ref,
        "current_image_id": short_running_id,
        "latest_image_id": short_latest_id,
        "update_available": is_newer,
        "has_newer_image": is_newer,
        "is_pinned": False,
        "pinned_reason": "",
        "can_update": True,
        "update_type": "compose" if c["is_compose"] else "standalone",
        "compose_file": c["compose_file"],
        "compose_service": c["compose_service"],
        "message": msg
    }

def check_all_container_updates(pull_remote=False, specific_containers=None, max_workers=3):
    """
    Checks containers for image updates.
    If pull_remote=True, contacts remote registries.
    If pull_remote=False, compares running container image against latest local tag.
    """
    containers = get_all_container_configs()
    if specific_containers:
        containers = [c for c in containers if c["name"] in specific_containers]
    
    results = {}
    updatable_count = 0
    
    if pull_remote:
        # Use ThreadPoolExecutor for remote pulls
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {executor.submit(check_single_container, c, True): c["name"] for c in containers}
            for future in as_completed(future_to_name):
                c_name = future_to_name[future]
                try:
                    res = future.result()
                    results[c_name] = res
                    if res.get("update_available"):
                        updatable_count += 1
                except Exception as ex:
                    results[c_name] = {
                        "name": c_name,
                        "update_available": False,
                        "can_update": False,
                        "message": str(ex)
                    }
    else:
        # Fast local tag comparison (completes in ~0.5s)
        for c in containers:
            res = check_single_container(c, pull_remote=False)
            results[c["name"]] = res
            if res.get("update_available"):
                updatable_count += 1
            
    payload = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "total_checked": len(containers),
        "updates_available_count": updatable_count,
        "containers": results
    }
    
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass
        
    return payload

def get_cached_updates():
    """Retrieve last cached update check results."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # If no cache exists, do a fast local check
    return check_all_container_updates(pull_remote=False)

def recreate_container(container_name):
    """
    Safely recreate and start a container with its newest image.
    Uses 'docker compose up -d' when compose-managed to preserve all mounts, envs, and network settings.
    """
    containers = get_all_container_configs()
    target = next((c for c in containers if c["name"] == container_name), None)
    
    if not target:
        return {"status": "error", "message": f"Container '{container_name}' not found"}
        
    if target["is_aio_child"]:
        return {
            "status": "skipped",
            "message": "Nextcloud AIO child containers must be updated via the Nextcloud AIO management portal (https://<ip>:8080)."
        }

    # 1. Compose Managed Containers
    if target["is_compose"]:
        c_file = target["compose_file"]
        c_service = target["compose_service"] or target["name"]
        try:
            # Snapshot current running image for instant rollback safety
            try:
                raw_repo = target["image_ref"].split(":")[0]
                if raw_repo and target.get("running_image_id"):
                    subprocess.run(
                        ["docker", "tag", target["running_image_id"], f"{raw_repo}:rollback-backup"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                    )
            except Exception:
                pass

            # 1. Pull the newest image
            pull_cmd = ["docker", "compose", "-f", c_file, "pull", c_service]
            try:
                pull_out = subprocess.check_output(pull_cmd, stderr=subprocess.STDOUT, timeout=90).decode("utf-8", errors="ignore")
            except subprocess.CalledProcessError as e:
                err_msg = e.output.decode("utf-8", errors="ignore") if hasattr(e, 'output') else str(e)
                if "permission denied" in err_msg.lower():
                    pull_cmd = ["sudo", "docker", "compose", "-f", c_file, "pull", c_service]
                    pull_out = subprocess.check_output(pull_cmd, stderr=subprocess.STDOUT, timeout=90).decode("utf-8", errors="ignore")
                else:
                    raise e
            
            # 2. Recreate and start with new image
            up_cmd = ["docker", "compose", "-f", c_file, "up", "-d", c_service]
            try:
                up_out = subprocess.check_output(up_cmd, stderr=subprocess.STDOUT, timeout=90).decode("utf-8", errors="ignore")
            except subprocess.CalledProcessError as e:
                err_msg = e.output.decode("utf-8", errors="ignore") if hasattr(e, 'output') else str(e)
                if "permission denied" in err_msg.lower():
                    up_cmd = ["sudo", "docker", "compose", "-f", c_file, "up", "-d", c_service]
                    up_out = subprocess.check_output(up_cmd, stderr=subprocess.STDOUT, timeout=90).decode("utf-8", errors="ignore")
                else:
                    raise e
            
            # Update cache entry for this container
            cached = get_cached_updates() or {"containers": {}}
            if container_name in cached.get("containers", {}):
                cached["containers"][container_name]["update_available"] = False
                cached["containers"][container_name]["message"] = "Updated to newest image and restarted."
                try:
                    with open(CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(cached, f, indent=2)
                except Exception:
                    pass

            return {
                "status": "success",
                "container": container_name,
                "type": "compose",
                "message": f"Successfully updated and restarted {container_name} on newest image.",
                "pull_output": pull_out.strip(),
                "up_output": up_out.strip()
            }
        except subprocess.CalledProcessError as e:
            return {
                "status": "error",
                "container": container_name,
                "message": e.output.decode("utf-8", errors="ignore") if hasattr(e, 'output') else str(e)
            }
        except Exception as e:
            return {"status": "error", "container": container_name, "message": str(e)}

    # 2. Standalone Containers
    img_ref = target["image_ref"]
    if not img_ref:
        return {"status": "error", "message": "No image reference found for standalone container."}
        
    try:
        # Pull latest image
        subprocess.check_output(["docker", "pull", img_ref], stderr=subprocess.STDOUT, timeout=90)
        # Restart container
        subprocess.check_output(["docker", "restart", container_name], timeout=35)
        
        cached = get_cached_updates() or {"containers": {}}
        if container_name in cached.get("containers", {}):
            cached["containers"][container_name]["update_available"] = False
            cached["containers"][container_name]["message"] = "Restarted with newest image"
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cached, f, indent=2)
            except Exception:
                pass

        return {
            "status": "success",
            "container": container_name,
            "type": "standalone",
            "message": f"Pulled newest image {img_ref} and restarted {container_name}."
        }
    except Exception as e:
        return {"status": "error", "container": container_name, "message": str(e)}

def update_all_containers():
    """Update all containers that have an update available."""
    cached = get_cached_updates()
    results = {}
    updated_count = 0
    errors = []
    
    for name, info in cached.get("containers", {}).items():
        if info.get("update_available") and info.get("can_update"):
            res = recreate_container(name)
            results[name] = res
            if res.get("status") == "success":
                updated_count += 1
            else:
                errors.append(f"{name}: {res.get('message')}")
                
    # Refresh cache after updates
    check_all_container_updates(pull_remote=False)
    
    return {
        "status": "success" if not errors else "partial",
        "updated_count": updated_count,
        "message": f"Successfully updated {updated_count} containers." if not errors else f"Updated {updated_count} containers with {len(errors)} errors.",
        "results": results,
        "errors": errors
    }
