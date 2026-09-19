#!/usr/bin/env python3
"""
task_manager.py - Homelab Automated Maintenance & System Task Engine
Features:
- Live discovery of host systemd timers (fstrim, apt-daily, logrotate, smart diagnostics, custom backups)
- Dynamic fallback task generator for containerized environments without host systemd access
- Persistent storage in data/tasks.json (excluded from Git and Docker images)
- Full CRUD operations: get, add, update, delete, detect
"""

import os
import re
import json
import time
import subprocess
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
TASKS_FILE = os.path.join(DATA_DIR, 'tasks.json')

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def detect_system_tasks():
    """
    Inspect the host machine for active scheduled operations.
    First tries systemctl list-timers (works on bare-metal and privileged containers with systemd).
    Falls back to detecting active host services (Docker, SMART disks, storage).
    """
    detected_tasks = []
    seen_titles = set()

    # 1. Try querying systemd timers
    try:
        cmd = ["systemctl", "list-timers", "--no-pager", "--full", "--all"]
        out = subprocess.check_output(cmd, timeout=3, stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
        lines = out.strip().splitlines()
        
        # Parse timer lines
        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("NEXT") or "timers listed" in line_str or line_str.startswith("Pass --all"):
                continue

            # Check if line contains a .timer unit
            m_unit = re.search(r'([a-zA-Z0-9_-]+)\.timer\s+([a-zA-Z0-9_-]+)\.service', line_str)
            if not m_unit:
                m_unit = re.search(r'([a-zA-Z0-9_-]+)\.timer', line_str)
            if not m_unit:
                continue

            timer_name = m_unit.group(1)
            service_name = m_unit.group(2) if len(m_unit.groups()) > 1 else timer_name

            # Skip noisy internal systemd timers
            if timer_name in ("sysstat-collect", "sysstat-summary", "update-notifier-motd", "update-notifier-download", "motd-news", "man-db"):
                continue

            title = ""
            tag = "System"
            desc = ""
            sched_time = "Daily"

            t_low = timer_name.lower()
            if "fstrim" in t_low:
                title = "SSD Periodic TRIM & Storage Discard"
                tag = "Storage"
                sched_time = "Weekly"
                desc = "Executes filesystem TRIM on mounted SSDs to restore flash write performance and longevity."
            elif "apt-daily-upgrade" in t_low or "unattended-upgrades" in t_low:
                title = "Unattended Security Package Upgrades"
                tag = "Updates"
                sched_time = "06:00 AM"
                desc = "Installs important security patches and critical distribution updates automatically."
            elif "apt-daily" in t_low or "dnf-makecache" in t_low:
                title = "System Package Index Refresh"
                tag = "Updates"
                sched_time = "Daily"
                desc = "Fetches latest package lists and CVE vulnerability metadata from upstream mirrors."
            elif "logrotate" in t_low:
                title = "System Log Rotation & Compression"
                tag = "Logs"
                sched_time = "00:00 AM"
                desc = "Compresses, archives, and prunes system and application log journals to prevent disk exhaustion."
            elif "smart" in t_low or "smartd" in t_low:
                title = "Drive SMART Health Diagnostic Scan"
                tag = "Disks"
                sched_time = "06:00 AM"
                desc = "Runs automated background diagnostic self-tests across all attached storage drives."
            elif "dpkg-db-backup" in t_low:
                title = "Package Database Integrity Snapshot"
                tag = "System"
                sched_time = "00:00 AM"
                desc = "Daily incremental snapshot of package manager database status and installed records."
            elif "tmpfiles" in t_low:
                title = "Temporary Cache & Tmpfile Auto-Purge"
                tag = "System"
                sched_time = "Daily"
                desc = "Removes stale temporary runtime files older than system retention window."
            elif "e2scrub" in t_low:
                title = "Ext4 Online Storage Scrub"
                tag = "Disks"
                sched_time = "Weekly"
                desc = "Scans filesystem metadata integrity across mounted Ext4 volumes."
            elif any(bk in t_low for bk in ("backup", "restic", "borg", "syncoid", "sanoid", "pve", "pbs", "rclone", "duplicati")):
                title = f"{timer_name.replace('-', ' ').title()} Backup Operation"
                tag = "Backup"
                sched_time = "Scheduled"
                desc = f"Automated backup schedule managed by systemd service {service_name}."
            else:
                title = f"{timer_name.replace('-', ' ').title()} Scheduled Task"
                tag = "System"
                sched_time = "Automated"
                desc = f"Host scheduled maintenance managed by {timer_name}.timer."

            if title not in seen_titles:
                seen_titles.add(title)
                detected_tasks.append({
                    "id": f"task_sys_{int(time.time())}_{len(detected_tasks)}",
                    "time": sched_time,
                    "title": title,
                    "tag": tag,
                    "status": "Active",
                    "desc": desc,
                    "unit": f"{timer_name}.timer",
                    "source": "systemd"
                })
        
        if detected_tasks:
            return detected_tasks

    except Exception:
        pass

    # 2. Fallback: Detect active host environment features
    # Check if Docker is running
    try:
        d_out = subprocess.check_output(["docker", "ps", "-q"], timeout=2, stderr=subprocess.DEVNULL)
        d_count = len(d_out.decode().strip().splitlines()) if d_out else 0
        if d_count > 0:
            detected_tasks.append({
                "id": f"task_dyn_{int(time.time())}_1",
                "time": "Daily",
                "title": f"Docker Fleet Health Sentinel ({d_count} Containers)",
                "tag": "Docker",
                "status": "Active",
                "desc": f"Monitors {d_count} container runtimes, inspects health checks, and checks for upstream image updates.",
                "source": "detected"
            })
    except Exception:
        pass

    # Check for storage drives
    try:
        import psutil
        disks = [p for p in psutil.disk_partitions(all=False) if p.fstype not in ('squashfs', 'tmpfs', 'overlay', '')]
        if disks:
            detected_tasks.append({
                "id": f"task_dyn_{int(time.time())}_2",
                "time": "06:00 AM",
                "title": f"Drive SMART Diagnostic & Scrub ({len(disks)} Volumes)",
                "tag": "Disks",
                "status": "Scheduled",
                "desc": f"Automated SMART health telemetry scan and wear-level check across {len(disks)} storage partitions.",
                "source": "detected"
            })
            detected_tasks.append({
                "id": f"task_dyn_{int(time.time())}_3",
                "time": "Weekly",
                "title": "SSD TRIM & Storage Discard Cycle",
                "tag": "Storage",
                "status": "Scheduled",
                "desc": "Periodic filesystem discard cycle to reclaim deleted flash blocks and maintain IOPS throughput.",
                "source": "detected"
            })
    except Exception:
        pass

    # Standard system log retention
    detected_tasks.append({
        "id": f"task_dyn_{int(time.time())}_4",
        "time": "00:00 AM",
        "title": "System Log Rotation & Journal Cleanup",
        "tag": "Logs",
        "status": "Active",
        "desc": "Daily compression and retention management of server activity logs and telemetry journals.",
        "source": "detected"
    })

    return detected_tasks

def get_tasks():
    """
    Retrieve maintenance tasks list.
    If tasks.json does not exist (fresh installation):
    Automatically triggers detect_system_tasks() to pull this specific system's tasks.
    """
    _ensure_data_dir()
    if not os.path.exists(TASKS_FILE):
        # Auto-detect tasks for this specific host
        initial_tasks = detect_system_tasks()
        save_tasks(initial_tasks)
        return initial_tasks

    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
            if isinstance(tasks, list):
                return tasks
    except Exception as e:
        print(f"[TaskManager] Error reading tasks.json: {e}")

    return []

def save_tasks(tasks):
    """Persist tasks list to data/tasks.json."""
    _ensure_data_dir()
    try:
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=2)
        return True
    except Exception as e:
        print(f"[TaskManager] Error saving tasks: {e}")
        return False

def add_task(task_data):
    """Add a new task."""
    tasks = get_tasks()
    task_id = task_data.get("id") or f"task_{int(time.time())}_{len(tasks) + 1}"
    new_task = {
        "id": task_id,
        "time": str(task_data.get("time", "Daily")).strip(),
        "title": str(task_data.get("title", "Custom Task")).strip(),
        "tag": str(task_data.get("tag", "System")).strip(),
        "status": str(task_data.get("status", "Scheduled")).strip(),
        "desc": str(task_data.get("desc", "")).strip(),
        "source": task_data.get("source", "user")
    }
    tasks.append(new_task)
    save_tasks(tasks)
    return new_task

def update_task(task_id, task_data):
    """Update an existing task by ID."""
    tasks = get_tasks()
    found = False
    for i, t in enumerate(tasks):
        if t.get("id") == task_id:
            tasks[i]["time"] = str(task_data.get("time", t.get("time"))).strip()
            tasks[i]["title"] = str(task_data.get("title", t.get("title"))).strip()
            tasks[i]["tag"] = str(task_data.get("tag", t.get("tag"))).strip()
            tasks[i]["status"] = str(task_data.get("status", t.get("status"))).strip()
            tasks[i]["desc"] = str(task_data.get("desc", t.get("desc"))).strip()
            found = True
            break
    if found:
        save_tasks(tasks)
        return tasks[i]
    return None

def delete_task(task_id):
    """Delete a task by ID."""
    tasks = get_tasks()
    orig_len = len(tasks)
    tasks = [t for t in tasks if t.get("id") != task_id]
    if len(tasks) < orig_len:
        save_tasks(tasks)
        return True
    return False
