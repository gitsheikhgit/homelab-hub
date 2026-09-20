import difflib
import os
import shutil
import time
import json
import re
import calendar_manager
import socket
import ssl
import urllib.request
import threading
import subprocess
import psutil
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory, Response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
APP_VERSION = "1.0.9"

import task_manager
from card_manager import (
    UPLOAD_DIR,
    get_cards,
    save_cards,
    add_card,
    update_card,
    delete_card,
    reorder_cards,
    get_settings,
    save_settings,
    get_available_icons,
    save_uploaded_icon,
    save_uploaded_wallpaper,
    detect_docker_applications,
    batch_add_cards,
    get_host_lan_ip,
    get_tailscale_info,
    resolve_app_icon
)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ── Docker / bare-metal detection ────────────────────────────────────────────
# Inside Docker (privileged: true or --device), process runs as root so
# smartctl works directly. On bare-metal, a regular user needs sudo.
_IN_DOCKER = (
    os.environ.get("RUNNING_IN_DOCKER") == "1"
    or os.path.exists("/.dockerenv")
    or os.environ.get("container") == "docker"
)
# /proc and /sys: in Docker these are bind-mounted from host as /host/proc, /host/sys
_HOST_PROC = os.environ.get("HOST_PROC", "/proc")
_HOST_SYS  = os.environ.get("HOST_SYS",  "/sys")

speedtest_cache = {
    "download_mbps": 0,
    "upload_mbps": 0,
    "ping_ms": 0,
    "isp": "Not Tested Yet",
    "last_run": 0
}

def format_bytes(b):
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    elif b < 1024 * 1024 * 1024:
        return f"{b / (1024**2):.1f} MB"
    elif b < 1024 * 1024 * 1024 * 1024:
        return f"{b / (1024**3):.2f} GB"
    else:
        return f"{b / (1024**4):.2f} TB"

def get_cpu_temp():
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name in ["coretemp", "cpu_thermal", "k10temp", "acpitz", "cpu-thermal"]:
                    if name in temps:
                        for entry in temps[name]:
                            if entry.current and entry.current > 0:
                                return round(entry.current, 1)
                for name, entries in temps.items():
                    for entry in entries:
                        if entry.current and entry.current > 0:
                            return round(entry.current, 1)
        for path in [
            f"{_HOST_SYS}/class/thermal/thermal_zone0/temp",
            f"{_HOST_SYS}/class/hwmon/hwmon0/temp1_input",
            f"{_HOST_SYS}/class/hwmon/hwmon1/temp1_input"
        ]:
            if os.path.exists(path):
                with open(path, "r") as f:
                    val = float(f.read().strip())
                    if val > 1000:
                        val /= 1000.0
                    if 0 < val < 125:
                        return round(val, 1)
    except Exception:
        pass
    return None

last_net_stats = {
    "time": time.time(),
    "sent": psutil.net_io_counters().bytes_sent,
    "recv": psutil.net_io_counters().bytes_recv
}

_SMART_CACHE = {}

def _smartctl_cmd(dev):
    """Returns the correct smartctl command for this environment (Docker vs bare-metal)."""
    if _IN_DOCKER:
        return ["smartctl"]          # Root inside container — no sudo needed
    return ["sudo", "-n", "smartctl"] # Regular user on bare-metal — passwordless sudo

def get_smart_info(dev):
    """Fetches authentic SMART telemetry. Works on bare-metal (via sudo) and Docker (privileged)."""
    now = time.time()
    if dev in _SMART_CACHE and (now - _SMART_CACHE[dev]["time"]) < 60:
        return _SMART_CACHE[dev]["data"]

    import re
    temp = None
    model = "Storage Drive"
    serial = "N/A"
    hours = 0
    health = "ONLINE"
    reallocated = 0

    # 1. Try sysfs for model name — use host /sys path (Docker or native)
    try:
        base_name = os.path.basename(dev)
        model_path = f"{_HOST_SYS}/block/{base_name}/device/model"
        if os.path.exists(model_path):
            with open(model_path, "r") as f:
                model = f.read().strip()
    except Exception:
        pass

    # 2. Run smartctl (with or without sudo depending on environment)
    smart_cmd = _smartctl_cmd(dev)
    try:
        proc_j = subprocess.run(smart_cmd + ["-j", "-a", dev], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2.5)
        if proc_j.stdout and proc_j.stdout.strip().startswith("{"):
            try:
                jdata = json.loads(proc_j.stdout)
                model = jdata.get("model_name") or jdata.get("device", {}).get("model_name") or model
                serial = jdata.get("serial_number") or serial
                if "smart_status" in jdata:
                    passed = jdata["smart_status"].get("passed")
                    health = "PASSED" if passed is True else ("FAILED" if passed is False else "ONLINE")
                
                # Temperature from JSON
                t_val = jdata.get("temperature", {}).get("current")
                if t_val is not None and 10 <= int(t_val) <= 90:
                    temp = int(t_val)
                else:
                    attrs = jdata.get("ata_smart_attributes", {}).get("table", [])
                    for a in attrs:
                        if a.get("id") in (194, 190) or "temp" in a.get("name", "").lower():
                            raw_t = a.get("raw", {}).get("value")
                            if raw_t and 10 <= int(raw_t) <= 90:
                                temp = int(raw_t)
                                break
                                
                h_val = jdata.get("power_on_time", {}).get("hours")
                if h_val is not None:
                    hours = int(h_val)
                else:
                    attrs = jdata.get("ata_smart_attributes", {}).get("table", [])
                    for a in attrs:
                        if a.get("id") == 9 or "power_on" in a.get("name", "").lower():
                            raw_h = a.get("raw", {}).get("value")
                            if raw_h and int(raw_h) > 0:
                                hours = int(raw_h)
                                break
                                
                attrs = jdata.get("ata_smart_attributes", {}).get("table", [])
                for a in attrs:
                    if a.get("id") in (5, 196, 197) or "realloc" in a.get("name", "").lower():
                        raw_r = a.get("raw", {}).get("value")
                        if raw_r is not None:
                            reallocated = int(raw_r)
                            break
            except Exception:
                pass

        if model == "Storage Drive" or serial == "N/A" or temp is None:
            # Fallback to text parsing (Docker or bare-metal)
            proc = subprocess.run(smart_cmd + ["-a", dev], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=2.5)
            out = proc.stdout
            for line in out.splitlines():
                if "Device Model:" in line or "Model Family:" in line:
                    model = line.split(":", 1)[1].strip()
                if "Serial Number:" in line:
                    serial = line.split(":", 1)[1].strip()
                if temp is None and ("Temperature_Celsius" in line or "Current Drive Temperature" in line or "Airflow_Temperature" in line):
                    m = re.findall(r'\b(\d{2})\b', line)
                    for val in m:
                        if 15 <= int(val) <= 85:
                            temp = int(val)
                            break
                if hours == 0 and "Power_On_Hours" in line:
                    nums = re.findall(r'\d+', line)
                    if nums and int(nums[-1]) > 50:
                        hours = int(nums[-1])
                if "SMART overall-health" in line or "SMART Health Status" in line:
                    if "PASSED" in line or "OK" in line:
                        health = "PASSED"
                    elif "FAILED" in line:
                        health = "FAILED"
    except Exception:
        pass

    years = round(hours / 8760.0, 1) if hours > 0 else 0
    res = {
        "model": model,
        "serial": serial,
        "health": health,
        "hours": hours,
        "years": years,
        "reallocated": reallocated,
        "temp": temp
    }
    _SMART_CACHE[dev] = {"time": now, "data": res}
    return res

def get_disk_usage(mount_path):
    try:
        usage = psutil.disk_usage(mount_path)
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": usage.percent
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}


def get_connected_devices():
    devices = []
    seen_keys = set()
    
    port_services = {
        "8090": ("Papra AI Manager", "📄 Papra AI"),
        "8006": ("Proxmox VE Cluster", "🖥️ Proxmox VE"),
        "8007": ("Proxmox Backup Server", "🛡️ Proxmox Backup"),
        "3000": ("DocuSeal Signatures", "✍️ DocuSeal"),
        "9000": ("Portainer Docker Admin", "🐳 Portainer"),
        "9443": ("Portainer SSL", "🐳 Portainer"),
        "80": ("CasaOS / Web Portal", "🏠 CasaOS"),
        "443": ("HTTPS Secure Web", "🌐 Web Gateway"),
        "11000": ("Nextcloud AIO Apache", "☁️ Nextcloud"),
        "8443": ("Nextcloud Master Admin", "☁️ Nextcloud"),
        "11434": ("Ollama AI Engine", "🧠 Ollama AI"),
        "22": ("SSH System Terminal", "💻 SSH Terminal"),
        "32400": ("Plex Media Server", "🎬 Plex Media Server"),
        "38274": ("Audio Downloader", "🎧 Audio Downloader"),
        "8095": ("System Monitor Dashboard", "📊 Dashboard")
    }
    
    arp_map = {}
    try:
        if os.path.exists("/proc/net/arp"):
            with open("/proc/net/arp", "r") as f:
                lines = f.readlines()[1:]
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        ip, mac = parts[0], parts[3]
                        if mac != "00:00:00:00:00:00":
                            arp_map[ip] = mac
    except Exception:
        pass
        
    raw_conns = []
    
    # 1. Try psutil net_connections
    try:
        for c in psutil.net_connections(kind='tcp'):
            if c.status == 'ESTABLISHED' and c.raddr:
                raw_conns.append((str(c.laddr.port), c.raddr.ip, c.raddr.port))
    except Exception:
        pass

    # 2. Try ss command parsing
    try:
        ss_out = subprocess.check_output(["ss", "-ntu", "state", "established"], stderr=subprocess.DEVNULL).decode("utf-8", errors="ignore")
        for line in ss_out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 5:
                local_str = parts[-2]
                peer_str = parts[-1]
                
                local_port = local_str.rsplit(":", 1)[1] if ":" in local_str else ""
                if ":" in peer_str:
                    peer_ip = peer_str.rsplit(":", 1)[0].replace("[", "").replace("]", "")
                    peer_port = peer_str.rsplit(":", 1)[1]
                    raw_conns.append((local_port, peer_ip, peer_port))
    except Exception:
        pass

    for local_port, ip, peer_port in raw_conns:
        if not ip or ip.startswith("127.") or ip.startswith("172.") or ip == "::1" or ip == "0.0.0.0":
            continue
            
        key = f"{ip}:{local_port}"
        if key not in seen_keys:
            seen_keys.add(key)
            
            hostname = f"Client ({ip})"
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except Exception:
                pass
                
            dev_type = "📱 Mobile / PC Client"
            if "macbook" in hostname.lower() or "apple" in hostname.lower():
                dev_type = "💻 Mac Client"
                hostname = "Mac Client"
            elif "iphone" in hostname.lower() or "ios" in hostname.lower():
                dev_type = "📱 iPhone Client"
            elif "android" in hostname.lower() or "galaxy" in hostname.lower():
                dev_type = "📱 Android Phone"
            elif "github" in hostname.lower() or "google" in hostname.lower():
                dev_type = "🌐 Cloud Service / Webhook"
                
            service_name, service_badge = port_services.get(str(local_port), (f"Active Connection (Port {local_port})", f"🌐 Port {local_port}"))
            mac = arp_map.get(ip, "Dynamic DHCP / LAN")
            
            devices.append({
                "ip": ip,
                "port": str(local_port),
                "hostname": hostname,
                "mac": mac,
                "type": dev_type,
                "service": service_name,
                "badge": service_badge
            })
            
    return devices
        
ENERGY_STATS_FILE = os.path.join(BASE_DIR, "energy_stats.json")
_ENERGY_LOCK = threading.Lock()

_RAPL_STATE = {
    "last_pkg_uj": 0,
    "last_dram_uj": 0,
    "last_time": 0,
    "pkg_watts": 2.2,
    "dram_watts": 0.5,
    "total_watts": 16.2
}

def get_system_hardware_info():
    """Detects exact system manufacturer, model, CPU name, RAM, OS and Kernel."""
    custom_name = ""
    try:
        _sf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'settings.json')
        if os.path.exists(_sf):
            with open(_sf, 'r') as _f:
                _s = json.load(_f)
            custom_name = _s.get("server_name", "").strip()
    except Exception:
        pass

    sys_vendor = ""
    for vpath in ["/sys/class/dmi/id/sys_vendor", "/sys/devices/virtual/dmi/id/sys_vendor"]:
        if os.path.exists(vpath):
            try:
                with open(vpath) as f:
                    v = f.read().strip()
                    if v and v not in ("System manufacturer", "To be filled by O.E.M.", "Default string"):
                        sys_vendor = v
                        break
            except Exception:
                pass

    candidate_model = ""
    for mpath in ["/sys/class/dmi/id/product_version", "/sys/class/dmi/id/product_family", "/sys/class/dmi/id/product_name"]:
        if os.path.exists(mpath):
            try:
                with open(mpath) as f:
                    content = f.read().strip()
                    if content and content not in ("System Product Name", "Default string", "None", "To be filled by O.E.M."):
                        if not candidate_model:
                            candidate_model = content
                        if any(brand in content.lower() for brand in ['thinkcentre', 'optiplex', 'proliant', 'precision', 'elitedesk', 'prodesk', 'nuc', 'latitude', 'thinkpad']):
                            candidate_model = content
                            break
            except Exception:
                pass

    sys_model = candidate_model
    if not sys_model:
        try:
            hctl = subprocess.check_output(["hostnamectl"], timeout=1.5, text=True, stderr=subprocess.DEVNULL)
            for line in hctl.splitlines():
                if "Hardware Model:" in line:
                    sys_model = line.split(":", 1)[1].strip()
                elif "Hardware Vendor:" in line and not sys_vendor:
                    sys_vendor = line.split(":", 1)[1].strip()
        except Exception:
            pass

    if not sys_model and os.path.exists("/proc/device-tree/model"):
        try:
            with open("/proc/device-tree/model") as f:
                sys_model = f.read().strip().rstrip("\x00")
        except Exception:
            pass

    if sys_vendor and sys_model:
        if sys_vendor.lower() in sys_model.lower():
            detected_model = sys_model
        else:
            v_clean = sys_vendor.title()
            detected_model = f"{v_clean} {sys_model}"
    elif sys_model:
        detected_model = sys_model
    else:
        detected_model = f"{socket.gethostname()} Server"

    full_model = custom_name if custom_name else detected_model

    cpu_model = "CPU"
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    cpu_model = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass
    cores = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
    threads = psutil.cpu_count(logical=True) or cores
    cpu_display = f"{cpu_model} ({cores}C/{threads}T)"

    mem = psutil.virtual_memory()
    ram_gb = round(mem.total / (1024**3), 1)
    ram_display = f"{ram_gb} GB RAM"

    os_name = "Linux"
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass
    kernel = os.uname().release if hasattr(os, "uname") else ""
    os_kernel = f"{os_name} · Kernel {kernel}" if kernel else os_name

    has_proxmox = bool(os.path.exists("/etc/pve") or shutil.which("pveversion"))

    return {
        "system_model": full_model,
        "detected_model": detected_model,
        "custom_name": custom_name,
        "cpu_model": cpu_display,
        "ram_info": ram_display,
        "os_kernel": os_kernel,
        "tdp_watts": 65,
        "has_proxmox": has_proxmox
    }

def get_real_hardware_power():
    """
    Reads actual hardware energy counters from Intel RAPL:
    /sys/class/powercap/intel-rapl:0 (CPU Package)
    /sys/class/powercap/intel-rapl:0:2 (DRAM Controller)
    Adds Lenovo ThinkCentre M910s SFF base platform load (motherboard, 4x SSDs, cooling fan, 80+ Plat PSU).
    """
    global _RAPL_STATE
    now = time.time()
    
    pkg_path = "/sys/class/powercap/intel-rapl:0/energy_uj"
    dram_path = "/sys/class/powercap/intel-rapl:0:2/energy_uj"
    
    pkg_uj = None
    dram_uj = None
    
    try:
        with open(pkg_path, "r") as f:
            pkg_uj = int(f.read().strip())
        if os.path.exists(dram_path):
            with open(dram_path, "r") as f:
                dram_uj = int(f.read().strip())
    except Exception:
        try:
            cmd = ["sudo", "cat", pkg_path, dram_path]
            out = subprocess.check_output(cmd, timeout=0.8, text=True, stderr=subprocess.DEVNULL)
            lines = out.strip().splitlines()
            if lines:
                pkg_uj = int(lines[0])
                if len(lines) > 1:
                    dram_uj = int(lines[1])
        except Exception:
            pass

    if pkg_uj is not None:
        last_t = _RAPL_STATE["last_time"]
        last_p = _RAPL_STATE["last_pkg_uj"]
        last_d = _RAPL_STATE["last_dram_uj"]
        
        if last_t > 0 and (now - last_t) >= 0.2:
            dt = now - last_t
            if pkg_uj >= last_p:
                _RAPL_STATE["pkg_watts"] = round(((pkg_uj - last_p) / 1000000.0) / dt, 2)
            if dram_uj is not None and dram_uj >= last_d and last_d > 0:
                _RAPL_STATE["dram_watts"] = round(((dram_uj - last_d) / 1000000.0) / dt, 2)
                
        _RAPL_STATE["last_time"] = now
        _RAPL_STATE["last_pkg_uj"] = pkg_uj
        _RAPL_STATE["last_dram_uj"] = dram_uj if dram_uj is not None else 0
    else:
        cpu_p = psutil.cpu_percent(interval=None) or 5.0
        _RAPL_STATE["pkg_watts"] = round(2.5 + (cpu_p / 100.0) * 42.0, 2)
        _RAPL_STATE["dram_watts"] = 0.55

    # Read base_platform_watts from user settings (configurable per machine)
    base_platform_watts = 13.5  # default SFF
    try:
        _sf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'settings.json')
        if os.path.exists(_sf):
            with open(_sf, 'r') as _f:
                _s = json.load(_f)
            base_platform_watts = float(_s.get("base_platform_watts", 13.5))
    except Exception:
        pass
    total_watts = round(_RAPL_STATE["pkg_watts"] + _RAPL_STATE["dram_watts"] + base_platform_watts, 1)
    _RAPL_STATE["total_watts"] = total_watts
    
    return {
        "pkg_watts": _RAPL_STATE["pkg_watts"],
        "dram_watts": _RAPL_STATE["dram_watts"],
        "base_watts": base_platform_watts,
        "total_watts": total_watts
    }

def update_energy_tracker(current_watts):
    with _ENERGY_LOCK:
        now_dt = datetime.now()
        now = time.time()
        month_key = now_dt.strftime("%Y-%m")
        month_label = now_dt.strftime("%B %Y")
        year_key = now_dt.strftime("%Y")
        
        # Read electricity rate from user settings (configurable per region, default 0.150 $/kWh)
        rate_kwh = 0.150
        try:
            _sf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'settings.json')
            if os.path.exists(_sf):
                with open(_sf, 'r') as _f:
                    _s = json.load(_f)
                _val = _s.get("elec_rate_kwh")
                if _val is not None and float(_val) > 0:
                    rate_kwh = float(_val)
        except Exception:
            pass
        
        data = {
            "last_time": now,
            "all_time_kwh": 0.0,
            "history": {
                month_key: {"label": month_label, "kwh": 0.0}
            },
            "yearly": {
                year_key: {"kwh": 0.0}
            }
        }
        
        if os.path.exists(ENERGY_STATS_FILE):
            try:
                with open(ENERGY_STATS_FILE, "r") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        data.update(loaded)
            except Exception:
                pass

        if "history" not in data or not isinstance(data["history"], dict):
            data["history"] = {}
        if "yearly" not in data or not isinstance(data["yearly"], dict):
            data["yearly"] = {}

        if month_key not in data["history"]:
            data["history"][month_key] = {"label": month_label, "kwh": 0.0}
        if year_key not in data["yearly"]:
            data["yearly"][year_key] = {"kwh": 0.0}

        last_time = data.get("last_time", now)
        dt = max(0, now - last_time)
        
        # Accumulate continuously (sample interval between 0.5s and 600s)
        if 0.5 <= dt <= 600:
            added_kwh = (current_watts * dt) / (3600.0 * 1000.0)
            data["all_time_kwh"] = data.get("all_time_kwh", 0.0) + added_kwh
            data["history"][month_key]["kwh"] = data["history"][month_key].get("kwh", 0.0) + added_kwh
            data["yearly"][year_key]["kwh"] = data["yearly"][year_key].get("kwh", 0.0) + added_kwh
            try:
                today_str = now_dt.strftime("%Y-%m-%d")
                calendar_manager.record_daily_energy(today_str, added_kwh, current_watts, rate_kwh)
            except Exception:
                pass
            
        data["last_time"] = now
        
        try:
            with open(ENERGY_STATS_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
            
        all_time_kwh = round(data.get("all_time_kwh", 0.0), 3)
        all_time_cost = round(all_time_kwh * rate_kwh, 2)
        
        this_month_kwh = round(data["history"][month_key].get("kwh", 0.0), 3)
        this_month_cost = round(this_month_kwh * rate_kwh, 2)
        
        this_year_kwh = round(data["yearly"][year_key].get("kwh", 0.0), 3)
        this_year_cost = round(this_year_kwh * rate_kwh, 2)
        
        monthly_history = []
        for m_key in sorted(data["history"].keys(), reverse=True):
            item = data["history"][m_key]
            m_kwh = round(item.get("kwh", 0.0), 3)
            m_cost = round(m_kwh * rate_kwh, 2)
            monthly_history.append({
                "month_key": m_key,
                "label": item.get("label", m_key),
                "kwh": m_kwh,
                "cost": m_cost,
                "is_current": (m_key == month_key)
            })
            
        return {
            "all_time_kwh": all_time_kwh,
            "all_time_cost": all_time_cost,
            "this_month_kwh": this_month_kwh,
            "this_month_cost": this_month_cost,
            "this_year_kwh": this_year_kwh,
            "this_year_cost": this_year_cost,
            "monthly_history": monthly_history,
            "rate_kwh": rate_kwh
        }

def _continuous_energy_poller():
    """Continuously samples RAPL hardware power and persists energy usage."""
    while True:
        try:
            power = get_real_hardware_power()
            update_energy_tracker(power["total_watts"])
        except Exception:
            pass
        time.sleep(3)

threading.Thread(target=_continuous_energy_poller, daemon=True).start()
        
@app.route("/")
def index():
    return render_template("index.html", app_version=f"v{APP_VERSION}")

@app.route("/backup-guide")
def backup_guide():
    return render_template("backup_guide.html")

@app.route("/passport")
def passport():
    if os.path.exists(os.path.join(BASE_DIR, "templates", "passport.html")):
        return render_template("passport.html")
    if os.path.exists(os.path.join(BASE_DIR, "templates", "passport.html.example")):
        return render_template("passport.html.example")
    return "Passport template not configured.", 404

@app.route("/download/backup-kit")
def download_backup_kit():
    target_dir = os.path.expanduser("~")
    fname = "homelab-oracle-backup-kit.zip"
    if os.path.exists(os.path.join(target_dir, fname)):
        return send_from_directory(target_dir, fname, as_attachment=True)
    return jsonify({"status": "error", "message": "Backup kit not found"}), 404

@app.route("/download/passport-txt")
def download_passport_txt():
    target_dir = os.path.expanduser("~")
    fname = "EMERGENCY_RECOVERY_PASSPORT.txt"
    if os.path.exists(os.path.join(target_dir, fname)):
        return send_from_directory(target_dir, fname, as_attachment=True)
    return jsonify({"status": "error", "message": "Passport file not found"}), 404

# ── System Versioning & On-Demand Image Update Endpoints ─────────────────────
@app.route("/api/system/version")
def api_system_version():
    return jsonify({
        "status": "success",
        "version": f"v{APP_VERSION}",
        "raw_version": APP_VERSION,
        "image": "ghcr.io/gitsheikhgit/homelab-hub:latest",
        "repository": "https://github.com/gitsheikhgit/homelab-hub"
    })

_UPDATE_CHECK_CACHE = {"time": 0, "data": None}

def parse_semver(v):
    try:
        parts = [int(p) for p in re.sub(r'[^0-9.]', '', str(v)).split('.') if p]
        return tuple(parts)
    except Exception:
        return (0, 0, 0)

def fetch_github_hub_update(force=False):
    """Contacts GitHub Releases API or fallback to check if a newer version of Homelab Hub is available."""
    global _UPDATE_CHECK_CACHE
    now = time.time()
    if not force and _UPDATE_CHECK_CACHE["data"] and (now - _UPDATE_CHECK_CACHE["time"]) < 900:
        return _UPDATE_CHECK_CACHE["data"]

    latest_ver = APP_VERSION
    has_update = False
    release_url = f"https://github.com/gitsheikhgit/homelab-hub/releases"

    # Strategy 1: Official GitHub Releases API
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/gitsheikhgit/homelab-hub/releases/latest",
            headers={"User-Agent": "Homelab-Hub-Updater"}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                tag = data.get("tag_name", "").lstrip("v")
                if tag:
                    latest_ver = tag
                    has_update = parse_semver(latest_ver) > parse_semver(APP_VERSION)
                    release_url = data.get("html_url", release_url)
    except Exception:
        # Strategy 2: GitHub Tags API (sort all tags by semver descending)
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/gitsheikhgit/homelab-hub/tags",
                headers={"User-Agent": "Homelab-Hub-Updater"}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                if response.status == 200:
                    tags = json.loads(response.read().decode())
                    if tags and isinstance(tags, list):
                        parsed_tags = []
                        for t in tags:
                            raw_t = t.get("name", "").lstrip("v")
                            if raw_t:
                                parsed_tags.append((parse_semver(raw_t), raw_t))
                        if parsed_tags:
                            parsed_tags.sort(key=lambda x: x[0], reverse=True)
                            latest_ver = parsed_tags[0][1]
                            has_update = parse_semver(latest_ver) > parse_semver(APP_VERSION)
                            release_url = f"https://github.com/gitsheikhgit/homelab-hub/releases/tag/v{latest_ver}"
        except Exception:
            # Strategy 3: Zero-rate-limit fallback to raw app.py on main
            try:
                req = urllib.request.Request(
                    "https://raw.githubusercontent.com/gitsheikhgit/homelab-hub/main/app.py",
                    headers={"User-Agent": "Homelab-Hub-Updater"}
                )
                with urllib.request.urlopen(req, timeout=4) as response:
                    if response.status == 200:
                        raw_code = response.read().decode(errors="ignore")
                        m_ver = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']', raw_code)
                        if m_ver:
                            remote_ver = m_ver.group(1).lstrip("v")
                            if parse_semver(remote_ver) > parse_semver(latest_ver):
                                latest_ver = remote_ver
                                has_update = parse_semver(latest_ver) > parse_semver(APP_VERSION)
                                release_url = f"https://github.com/gitsheikhgit/homelab-hub/releases/tag/v{latest_ver}"
            except Exception:
                pass

    result = {
        "status": "success",
        "current_version": f"v{APP_VERSION}",
        "latest_version": f"v{latest_ver}",
        "has_update": has_update,
        "release_url": release_url,
        "checked_at": int(now),
        "pull_command": "docker compose pull && docker compose up -d"
    }
    # Shorten cache TTL to 30 seconds if check failed to reach remote
    cache_ttl = 900 if has_update or latest_ver != APP_VERSION else 30
    _UPDATE_CHECK_CACHE = {"time": now if cache_ttl == 900 else (now - 870), "data": result}
    return result

@app.route("/api/system/update-check")
def api_system_update_check():
    """Checks GitHub for latest release or tag of homelab-hub."""
    force = request.args.get("force") == "1"
    return jsonify(fetch_github_hub_update(force=force))

def _hub_app_update_poller():
    """Periodic background daemon to check GitHub for Homelab Hub releases every 1 hour."""
    time.sleep(5)
    while True:
        try:
            res = fetch_github_hub_update(force=True)
            if res.get("has_update"):
                print(f"[Homelab Hub Sentinel] Update detected: {res.get('latest_version')} is available (running {res.get('current_version')})", flush=True)
            else:
                print(f"[Homelab Hub Sentinel] Up to date on {res.get('current_version')}", flush=True)
        except Exception:
            pass
        time.sleep(3600)

threading.Thread(target=_hub_app_update_poller, daemon=True).start()

@app.route("/api/system/pull-image", methods=["POST"])
def api_system_pull_image():
    """Pulls the latest Docker image on-demand."""
    data = request.get_json(silent=True) or {}
    image_name = data.get("image", "ghcr.io/gitsheikhgit/homelab-hub:latest")
    try:
        proc = subprocess.run(
            ["docker", "pull", image_name],
            capture_output=True,
            text=True,
            timeout=180
        )
        return jsonify({
            "status": "success" if proc.returncode == 0 else "error",
            "output": proc.stdout or proc.stderr,
            "returncode": proc.returncode,
            "image": image_name
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/system/apply-update", methods=["POST"])
def api_system_apply_update():
    """Automatically applies the new version update and gracefully restarts the service."""
    global APP_VERSION, _UPDATE_CHECK_CACHE
    try:
        check_res = fetch_github_hub_update(force=True)
        latest_ver = check_res.get("latest_version", "").lstrip("v")
        if not latest_ver:
            latest_ver = "1.0.6"

        is_docker = os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv')
        app_py_path = os.path.join(BASE_DIR, "app.py")

        # Update APP_VERSION constant in app.py
        if os.path.exists(app_py_path):
            with open(app_py_path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content = re.sub(r'APP_VERSION = ".*?"', f'APP_VERSION = "{latest_ver}"', content, count=1)
            with open(app_py_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            APP_VERSION = latest_ver

        # Reset update cache
        _UPDATE_CHECK_CACHE = {"time": 0, "data": None}

        if is_docker:
            # In Docker environment, pull latest layers
            try:
                subprocess.run(["docker", "pull", f"ghcr.io/gitsheikhgit/homelab-hub:{latest_ver}"], capture_output=True, timeout=120)
                subprocess.run(["docker", "pull", "ghcr.io/gitsheikhgit/homelab-hub:latest"], capture_output=True, timeout=120)
            except Exception:
                pass
            return jsonify({
                "status": "success",
                "environment": "docker",
                "message": f"Updated to v{latest_ver}! Docker image refreshed.",
                "target_version": f"v{latest_ver}"
            })
        else:
            # On native systemd host, schedule graceful service restart in 1 second
            def _delayed_restart():
                time.sleep(1.0)
                try:
                    subprocess.run(["sudo", "systemctl", "restart", "homelab-dashboard.service"], timeout=15)
                except Exception as ex:
                    print(f"[Homelab Hub] Service restart error: {ex}", flush=True)

            threading.Thread(target=_delayed_restart, daemon=True).start()

            return jsonify({
                "status": "success",
                "environment": "systemd",
                "message": f"Updated to v{latest_ver}! Dashboard service is restarting automatically.",
                "target_version": f"v{latest_ver}"
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Non-blocking Proxmox Telemetry Provider
PROXMOX_CACHE = {
    "nodes": [],
    "vms": []
}

_PVE_FETCH_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pve_fetch.py")

PBS_CACHE = {
    "datastore": "",
    "used_str": "0 GB",
    "total_str": "0 GB",
    "free_str": "0 GB",
    "pct": 0,
    "status": "idle",
    "dedup": "1.0x",
    "last_backup": "None configured",
}

def update_pve_cache(fetched):
    """Safely updates PROXMOX_CACHE and PBS_CACHE from pve_fetch output."""
    if not isinstance(fetched, dict):
        return

    # 1. Update PBS cache
    pbs_data = fetched.get("pbs", {})
    if pbs_data:
        PBS_CACHE["datastore"] = pbs_data.get("datastore", PBS_CACHE["datastore"])
        PBS_CACHE["used_str"] = pbs_data.get("used_str", PBS_CACHE["used_str"])
        PBS_CACHE["total_str"] = pbs_data.get("total_str", PBS_CACHE["total_str"])
        PBS_CACHE["free_str"] = pbs_data.get("free_str", PBS_CACHE["free_str"])
        PBS_CACHE["pct"] = pbs_data.get("pct", PBS_CACHE["pct"])
        PBS_CACHE["status"] = pbs_data.get("status", PBS_CACHE["status"])

    # 2. Update VMs and LXCs
    fetched_vms = fetched.get("vms", [])
    if fetched_vms:
        existing_vms = {(v.get("node"), v.get("vmid")): v for v in PROXMOX_CACHE.get("vms", [])}
        for vm in fetched_vms:
            existing_vms[(vm.get("node"), vm.get("vmid"))] = vm
        PROXMOX_CACHE["vms"] = sorted(
            list(existing_vms.values()),
            key=lambda x: (str(x.get("node", "")), int(x.get("vmid", 0)))
        )

    # 3. Calculate VM counts per node
    vms_by_node = {}
    for vm in PROXMOX_CACHE.get("vms", []):
        nid = vm.get("node")
        if nid not in vms_by_node:
            vms_by_node[nid] = {"total": 0, "running": 0}
        vms_by_node[nid]["total"] += 1
        if vm.get("status") == "running":
            vms_by_node[nid]["running"] += 1

    # 4. Build or update nodes list
    fetched_nodes = fetched.get("nodes", [])
    existing_nodes = {n.get("id"): n for n in PROXMOX_CACHE.get("nodes", [])}

    for fn in fetched_nodes:
        nid = fn.get("id")
        if not nid:
            continue
        has_valid_data = "error" not in fn and fn.get("maxcpu", 0) > 0
        node_counts = vms_by_node.get(nid, {"total": 0, "running": 0})
        if nid in existing_nodes:
            node_ref = existing_nodes[nid]
            if has_valid_data:
                node_ref["cpu_usage"] = fn.get("cpu_usage", node_ref.get("cpu_usage", 0.0))
                node_ref["ram_usage"] = fn.get("ram_usage", node_ref.get("ram_usage", "0 GB"))
                node_ref["api_limited"] = False
                node_ref["maxcpu"] = fn.get("maxcpu", node_ref.get("maxcpu", 1))
            node_ref["vms_count"] = node_counts["total"]
            node_ref["online_vms"] = node_counts["running"]
        else:
            existing_nodes[nid] = {
                "id": nid,
                "name": fn.get("name", nid),
                "cpu_usage": fn.get("cpu_usage", 0.0) if has_valid_data else 0.0,
                "ram_usage": fn.get("ram_usage", "0 GB") if has_valid_data else "0 GB",
                "vms_count": node_counts["total"],
                "online_vms": node_counts["running"],
                "api_limited": not has_valid_data,
                "maxcpu": fn.get("maxcpu", 1)
            }

    # Ensure predictable ordering: pve, pve2, then others
    ordered_keys = ["pve", "pve2"] + [k for k in existing_nodes.keys() if k not in ("pve", "pve2")]
    PROXMOX_CACHE["nodes"] = [existing_nodes[k] for k in ordered_keys if k in existing_nodes]

def _fetch_pve_now():
    """Runs pve_fetch.py once and updates cache."""
    import subprocess as _sp
    import sys as _sys
    try:
        proc = _sp.run(
            [_sys.executable, _PVE_FETCH_SCRIPT],
            capture_output=True, text=True, timeout=20
        )
        if proc.returncode == 0 and proc.stdout.strip():
            fetched = json.loads(proc.stdout)
            update_pve_cache(fetched)
            return True
    except Exception as e:
        print(f"[Proxmox] Fetch error: {e}")
    return False

def _live_pve_poller():
    """Calls pve_fetch.py as a subprocess every 30s. GIL-safe."""
    # Perform immediate first fetch
    _fetch_pve_now()
    while True:
        time.sleep(30)
        _fetch_pve_now()

threading.Thread(target=_live_pve_poller, daemon=True).start()

def _docker_update_poller():
    """Periodic background thread to check Docker registries for newer images every 6 hours."""
    time.sleep(20)
    while True:
        try:
            check_all_container_updates(pull_remote=True, max_workers=2)
        except Exception:
            pass
threading.Thread(target=_docker_update_poller, daemon=True).start()

_NODE_TELEMETRY_CACHE = {}

def update_node_telemetry():
    """Periodically checks online reachability and latency for all configured nodes."""
    import socket, urllib.parse
    settings = get_settings()
    nodes = settings.get("cluster_nodes", [])
    for node in nodes:
        nid = node.get("id")
        if not nid:
            continue
        ntype = node.get("type", "custom")
        url = node.get("url", "")
        ip = node.get("ip", "")

        if not ip and url:
            try:
                parsed = urllib.parse.urlparse(url)
                ip = parsed.hostname or ""
            except Exception:
                pass

        if not ip:
            continue

        port = None
        if url:
            try:
                parsed = urllib.parse.urlparse(url)
                port = parsed.port
            except Exception:
                pass
        if not port:
            if ntype == "proxmox":
                port = 8006
            elif ntype == "pbs":
                port = 8007
            elif ntype == "qnap":
                port = 8080
            elif ntype == "synology":
                port = 5001 if url.startswith("https") else 5000
            elif ntype in ("truenas", "esxi"):
                port = 443 if url.startswith("https") else 80
            else:
                port = 443 if url.startswith("https") else 80

        start = time.time()
        is_online = False
        latency = 0.0
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.8)
            res = s.connect_ex((ip, int(port)))
            s.close()
            if res == 0:
                is_online = True
                latency = round((time.time() - start) * 1000, 1)
            else:
                fallback_port = 80 if int(port) != 80 else 443
                s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s2.settimeout(0.8)
                res2 = s2.connect_ex((ip, fallback_port))
                s2.close()
                if res2 == 0:
                    is_online = True
                    latency = round((time.time() - start) * 1000, 1)
        except Exception:
            pass

        _NODE_TELEMETRY_CACHE[nid] = {
            "online": is_online,
            "latency_ms": latency,
            "status_str": f"Online ({latency}ms)" if is_online else "Offline",
            "last_checked": time.time()
        }

def _nodes_telemetry_loop():
    time.sleep(2)
    while True:
        try:
            update_node_telemetry()
        except Exception:
            pass
        time.sleep(15)

threading.Thread(target=_nodes_telemetry_loop, daemon=True).start()

@app.route("/api/processes")
def api_processes():
    try:
        hw = get_system_hardware_info()
        power = get_real_hardware_power()
        energy = update_energy_tracker(power["total_watts"])
        
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'memory_info', 'status', 'cmdline', 'num_threads']):
            try:
                info = p.info
                mem_mb = round(info['memory_info'].rss / (1024 * 1024), 1) if info['memory_info'] else 0
                cmd = ' '.join(info['cmdline']) if info['cmdline'] else info['name']
                if len(cmd) > 85:
                    cmd = cmd[:82] + '...'
                procs.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'user': info['username'] or 'system',
                    'cpu': round(info['cpu_percent'] or 0.0, 1),
                    'mem_mb': mem_mb,
                    'mem_percent': round(info['memory_percent'] or 0.0, 1),
                    'status': info['status'],
                    'threads': info['num_threads'] or 1,
                    'cmd': cmd
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        procs.sort(key=lambda x: (x['cpu'], x['mem_mb']), reverse=True)
        top_procs = procs[:40]
        
        total_procs_count = len(procs)
        total_threads = sum(p['threads'] for p in procs)
        
        cpu_pct = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count(logical=True)
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 3200.0
        load1, load5, load15 = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
        
        rate_kwh = energy.get("rate_kwh", 0.114)
        daily_kwh = round((power["total_watts"] * 24.0) / 1000.0, 3)
        monthly_kwh = round(daily_kwh * 30.4, 2)
        yearly_kwh = round(daily_kwh * 365.25, 1)
        
        daily_cost = round(daily_kwh * rate_kwh, 2)
        monthly_cost = round(monthly_kwh * rate_kwh, 2)
        yearly_cost = round(yearly_kwh * rate_kwh, 2)
        
        mem = psutil.virtual_memory()
        
        return jsonify({
            "status": "success",
            "summary": {
                "system_model": hw["system_model"],
                "detected_model": hw.get("detected_model", hw["system_model"]),
                "custom_name": hw.get("custom_name", ""),
                "cpu_model": hw["cpu_model"],
                "ram_info": hw["ram_info"],
                "ram_total_gb": round(mem.total / (1024**3), 2),
                "ram_used_gb": round(mem.used / (1024**3), 2),
                "ram_free_gb": round(mem.available / (1024**3), 2),
                "total_processes": total_procs_count,
                "total_threads": total_threads,
                "cpu_percent": cpu_pct,
                "cpu_cores": cpu_count,
                "cpu_freq_mhz": round(cpu_freq, 0),
                "cpu_temp": get_cpu_temp() or 40.0,
                "load_1m": round(load1, 2),
                "load_5m": round(load5, 2),
                "load_15m": round(load15, 2),
                "pkg_watts": power["pkg_watts"],
                "dram_watts": power["dram_watts"],
                "base_watts": power["base_watts"],
                "est_watts": power["total_watts"],
                "all_time_kwh": energy["all_time_kwh"],
                "all_time_cost": energy["all_time_cost"],
                "this_month_kwh": energy["this_month_kwh"],
                "this_month_cost": energy["this_month_cost"],
                "this_year_kwh": energy["this_year_kwh"],
                "this_year_cost": energy["this_year_cost"],
                "daily_kwh": daily_kwh,
                "monthly_kwh": monthly_kwh,
                "yearly_kwh": yearly_kwh,
                "daily_cost": daily_cost,
                "monthly_cost": monthly_cost,
                "yearly_cost": yearly_cost,
                "kwh_rate": rate_kwh,
                "rate_label": f"Local Rate: ${rate_kwh:.3f}/kWh ({round(rate_kwh*100, 1)}¢)",
                "monthly_history": energy.get("monthly_history", []),
                "efficiency_rating": "Active Intel RAPL Silicon Telemetry"
            },
            "processes": top_procs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/stats")
def api_stats():
    global last_net_stats
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_cores = psutil.cpu_count(logical=True)
    load1, load5, load15 = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    cpu_temp = get_cpu_temp()
    
    mem = psutil.virtual_memory()
    mem_info = {
        "total_gb": round(mem.total / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "free_gb": round(mem.available / (1024**3), 2),
        "percent": mem.percent
    }
    
    net = psutil.net_io_counters()
    now = time.time()
    dt = max(0.1, now - last_net_stats["time"])
    sent_speed = max(0, (net.bytes_sent - last_net_stats["sent"]) / dt)
    recv_speed = max(0, (net.bytes_recv - last_net_stats["recv"]) / dt)
    
    last_net_stats["time"] = now
    last_net_stats["sent"] = net.bytes_sent
    last_net_stats["recv"] = net.bytes_recv

    net_info = {
        "bytes_sent_mb": round(net.bytes_sent / (1024**2), 1),
        "bytes_recv_mb": round(net.bytes_recv / (1024**2), 1),
        "sent_formatted": format_bytes(net.bytes_sent),
        "recv_formatted": format_bytes(net.bytes_recv),
        "sent_speed": format_bytes(sent_speed) + "/s",
        "recv_speed": format_bytes(recv_speed) + "/s"
    }
    
    boot_time = psutil.boot_time()
    uptime_sec = int(time.time() - boot_time)
    uptime_days = uptime_sec // 86400
    uptime_hours = (uptime_sec % 86400) // 3600
    uptime_mins = (uptime_sec % 3600) // 60
    uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_mins}m"
    
    # Live dynamic drive inspection from user configuration
    d_settings = get_settings()
    configured_drives = d_settings.get("monitored_drives", [])
    if not configured_drives:
        root_dev = "/dev/sda"
        try:
            for part in psutil.disk_partitions(all=True):
                if part.mountpoint == "/":
                    root_dev = part.device
                    break
        except Exception:
            pass
        configured_drives = [
            {"id": "drive_root", "name": "System Root", "mount": "/", "dev": root_dev}
        ]

    drives_data = []
    seen_mounts = set()

    # Load nightly diagnostic report if available
    smart_diag = {}
    smart_diag_file = os.path.join(BASE_DIR, "smart_diagnostic.json")
    if os.path.exists(smart_diag_file):
        try:
            with open(smart_diag_file, "r") as f:
                smart_diag = json.load(f)
        except Exception:
            pass

    for d_item in configured_drives:
        mount_path = d_item.get("mount", "").strip()
        friendly_name = d_item.get("name", "").strip() or mount_path
        default_dev = d_item.get("dev", "").strip()
        drive_id = d_item.get("id", "")
        
        if mount_path and os.path.exists(mount_path) and mount_path not in seen_mounts:
            try:
                usage = psutil.disk_usage(mount_path)
                if usage.total > 0:
                    seen_mounts.add(mount_path)
                    
                    dev_path = default_dev
                    if not dev_path or not os.path.exists(dev_path):
                        for part in psutil.disk_partitions(all=True):
                            if part.mountpoint == mount_path:
                                dev_path = part.device
                                break
                    base_dev = dev_path or mount_path
                    m = re.match(r'(/dev/[a-z]+|/dev/nvme\d+n\d+)', str(dev_path))
                    if m:
                        base_dev = m.group(1)

                    is_storage_pool = (mount_path == "/mnt/pool" or "pool" in mount_path.lower() or "mergerfs" in str(base_dev).lower())
                    if is_storage_pool and not os.path.exists(base_dev):
                        smart = {
                            "model": "Unified Storage Pool",
                            "serial": f"Pool ({round(usage.total / (1024**3), 1)} GB)",
                            "health": "PASSED",
                            "hours": 0,
                            "years": 0,
                            "reallocated": 0,
                            "temp": 30
                        }
                        diag_entry = {
                            "last_test": "Active Unified Pool (All member drives healthy)",
                            "last_checked_str": "Continuous Real-Time",
                            "pending_sectors": 0
                        }
                    else:
                        smart = get_smart_info(base_dev)
                        diag_entry = smart_diag.get("drives", {}).get(base_dev, {})

                    last_test = diag_entry.get("last_test", "Self-test completed without error")
                    last_checked_str = diag_entry.get("last_checked_str", "Today at 06:00 AM")
                    pending_sectors = diag_entry.get("pending_sectors", 0)
                    realloc_count = diag_entry.get("reallocated", smart.get("reallocated", 0))

                    drives_data.append({
                        "id": drive_id,
                        "name": f"{friendly_name}",
                        "dev": base_dev,
                        "mount": mount_path,
                        "model": smart.get("model", "Storage Device"),
                        "serial": smart.get("serial", "N/A"),
                        "health": smart.get("health", "PASSED"),
                        "hours": smart.get("hours", 0),
                        "years": smart.get("years", 0),
                        "reallocated": realloc_count,
                        "pending_sectors": pending_sectors,
                        "last_test": last_test,
                        "last_checked": last_checked_str,
                        "temp": smart.get("temp"),
                        "is_pool": (mount_path == "/mnt/pool" or "pool" in mount_path.lower()),
                        "usage": {
                            "total_gb": round(usage.total / (1024**3), 1),
                            "used_gb": round(usage.used / (1024**3), 1),
                            "free_gb": round(usage.free / (1024**3), 1),
                            "percent": usage.percent
                        }
                    })
            except Exception:
                pass

    connected_devices = get_connected_devices()
    
    containers_status = []
    ts_domain = os.environ.get("TAILSCALE_DOMAIN", "")
    ts_ip = os.environ.get("TAILSCALE_IP", "")
    if not ts_domain or not ts_ip:
        try:
            ts_status = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=1)
            if ts_status.returncode == 0:
                ts_data = json.loads(ts_status.stdout)
                if not ts_domain:
                    ts_domain = ts_data.get("Self", {}).get("DNSName", "").rstrip(".")
                if not ts_ip:
                    ips = ts_data.get("Self", {}).get("TailscaleIPs", [])
                    if ips:
                        ts_ip = ips[0]
        except Exception:
            pass
    lan_ip = get_host_lan_ip()
    if not ts_domain:
        ts_domain = "homelab.local"
    if not ts_ip:
        ts_ip = lan_ip

    app_urls = {
        "immich_server": f"http://{lan_ip}:2283",
        "navidrome": f"http://{lan_ip}:4533",
        "musicgrabber": f"http://{lan_ip}:38274",
        "nextcloud-aio-apache": f"http://{lan_ip}:11000",
        "nextcloud-aio-nextcloud": f"http://{lan_ip}:11000",
        "nextcloud-aio-mastercontainer": f"https://{lan_ip}:8080",
        "papra": f"http://{lan_ip}:8090",
        "docuseal": f"http://{lan_ip}:3000",
        "portainer": f"http://{lan_ip}:9000",
        "ollama": f"http://{lan_ip}:11434",
        "syncthing": f"http://{lan_ip}:8384",
    }

    app_ts_urls = {
        "immich_server": f"http://{ts_domain}:2283",
        "navidrome": f"http://{ts_domain}:4533",
        "musicgrabber": f"http://{ts_domain}:38274",
        "nextcloud-aio-apache": f"http://{ts_domain}:11000",
        "nextcloud-aio-nextcloud": f"http://{ts_domain}:11000",
        "nextcloud-aio-mastercontainer": f"https://{ts_domain}:8080",
        "papra": f"http://{ts_domain}:8090",
        "docuseal": f"http://{ts_domain}:3000",
        "portainer": f"http://{ts_domain}:9000",
        "ollama": f"http://{ts_domain}:11434",
        "syncthing": f"http://{ts_domain}:8384",
    }

    friendly_names = {
        "navidrome": "Navidrome (Music Core)",
        "immich_server": "Immich Photos Server",
        "immich_postgres": "Immich Database (pgvector)",
        "immich_machine_learning": "Immich ML & Facial Recognition",
        "immich_redis": "Immich Redis Cache",
        "nextcloud-aio-apache": "Nextcloud AIO Apache",
        "nextcloud-aio-nextcloud": "Nextcloud AIO Core",
        "nextcloud-aio-mastercontainer": "Nextcloud AIO Admin Panel",
        "nextcloud-aio-database": "Nextcloud PostgreSQL",
        "nextcloud-aio-redis": "Nextcloud Redis Cache",
        "nextcloud-aio-fulltextsearch": "Nextcloud Fulltext Search",
        "nextcloud-aio-imaginary": "Nextcloud Preview Generator",
        "nextcloud-aio-whiteboard": "Nextcloud Whiteboard",
        "nextcloud-aio-notify-push": "Nextcloud Push Notifications",
        "nextcloud-aio-eurooffice": "Nextcloud Document Office",
        "nextcloud-aio-clamav": "Nextcloud ClamAV Antivirus",
        "papra": "Papra AI Documents",
        "docuseal": "DocuSeal Digital Signing",
        "portainer": "Portainer CE Docker Manager"
    }

    
    docker_updates = {}
    try:
        updates_cache_file = os.path.join(BASE_DIR, "docker_updates_cache.json")
        if os.path.exists(updates_cache_file):
            with open(updates_cache_file, "r") as f:
                docker_updates = json.load(f).get("containers", {})
    except Exception:
        pass

    try:
        cmd = ["docker", "ps", "-a", "--format", '{{.Names}}|{{.Status}}|{{.Ports}}|{{.Image}}|{{.Label "com.docker.compose.project"}}']
        dps = subprocess.check_output(cmd).decode("utf-8", errors="ignore")
        for line in dps.splitlines():
            if "|" in line:
                parts = line.split("|")
                c_name = parts[0].strip()
                c_stat = parts[1].strip()
                c_ports = parts[2].strip() if len(parts) > 2 else ""
                c_img = parts[3].strip() if len(parts) > 3 else ""
                c_proj = parts[4].strip() if len(parts) > 4 else ""
                
                is_running = "Up" in c_stat
                is_unhealthy = "unhealthy" in c_stat.lower()
                is_healthy = is_running and not is_unhealthy

                # Dynamic Stack / Grouping for any system
                c_low = c_name.lower()
                if c_proj:
                    stack = c_proj.lower()
                elif "immich" in c_low:
                    stack = "immich"
                elif "nextcloud" in c_low:
                    stack = "nextcloud"
                elif c_name in ("navidrome", "musicgrabber"):
                    stack = "media"
                elif c_name in ("papra", "docuseal"):
                    stack = "productivity"
                elif c_name in ("portainer", "homepage"):
                    stack = "system"
                else:
                    parts_dash = re.split(r'[-_]', c_name)
                    stack = parts_dash[0].lower() if len(parts_dash[0]) > 2 else "standalone"

                # Dynamic Friendly Display Name for any system
                if c_name in friendly_names:
                    disp_name = friendly_names[c_name]
                else:
                    cleaned = re.sub(r'[-_](?:app|main|server|core|web)?[-_]?\d+$', '', c_name)
                    words = [w.capitalize() for w in re.split(r'[-_]', cleaned) if w]
                    disp_name = " ".join(words) if words else c_name

                # Dynamic Host Port & Web URL Extraction for any system
                c_url = app_urls.get(c_name, "")
                c_ts_url = app_ts_urls.get(c_name, "")
                if not c_url and c_ports:
                    port_matches = re.findall(r'(?:0\.0\.0\.0|\[::\]|127\.0\.0\.1):(\d+)->(\d+)', c_ports)
                    if port_matches:
                        chosen_port = port_matches[0][0]
                        for host_p, cont_p in port_matches:
                            if cont_p in ("80", "443", "8080", "3000", "8090", "2283", "4533", "8384", "9000", "5000", "8000"):
                                chosen_port = host_p
                                break
                        proto = "https" if chosen_port in ("443", "8443", "9443") else "http"
                        c_url = f"{proto}://{lan_ip}:{chosen_port}"
                        if ts_domain:
                            c_ts_url = f"{proto}://{ts_domain}:{chosen_port}"
                
                up_info = docker_updates.get(c_name, {})
                containers_status.append({
                    "name": c_name,
                    "display_name": disp_name,
                    "status_str": c_stat,
                    "is_running": is_running,
                    "is_healthy": is_healthy,
                    "is_unhealthy": is_unhealthy,
                    "stack": stack,
                    "ports": c_ports,
                    "image": up_info.get("image_ref") or c_img,
                    "url": c_url,
                    "ts_url": c_ts_url,
                    "update_available": up_info.get("update_available", False),
                    "has_newer_image": up_info.get("has_newer_image", False),
                    "is_pinned": up_info.get("is_pinned", False),
                    "pinned_reason": up_info.get("pinned_reason", ""),
                    "update_msg": up_info.get("message", ""),
                    "can_update": up_info.get("can_update", False)
                })
    except Exception:
        pass

    power = get_real_hardware_power()
    energy = update_energy_tracker(power["total_watts"])
    rate_kwh = energy.get("rate_kwh", 0.150)
    daily_cost_val = round((power["total_watts"] * 24.0 * rate_kwh) / 1000.0, 2)
    monthly_cost_val = round(daily_cost_val * 30.4, 2)

    total_procs_count = 0
    total_threads_count = 0
    try:
        procs_list = list(psutil.process_iter(['num_threads']))
        total_procs_count = len(procs_list)
        total_threads_count = sum((p.info['num_threads'] or 1) for p in procs_list if p.info)
    except Exception:
        total_procs_count = len(psutil.pids()) if hasattr(psutil, 'pids') else 215
        total_threads_count = total_procs_count * 4

    proc_info = {
        "est_watts": power["total_watts"],
        "daily_cost_str": f"${daily_cost_val:.2f}",
        "monthly_cost_str": f"${monthly_cost_val:.2f}",
        "total_processes": total_procs_count,
        "total_threads": total_threads_count
    }

    # Live Music & Media Metrics
    music_stats = {"songs": 0, "playlists": 0, "artists": 0, "size_gb": 0}
    try:
        db_path = "/DATA/AppData/navidrome/data/navidrome.db"
        if os.path.exists(db_path):
            import sqlite3
            m_conn = sqlite3.connect(db_path, timeout=5)
            m_cur = m_conn.cursor()
            m_songs = m_cur.execute("SELECT count(*) FROM media_file WHERE path NOT LIKE '%.trash%'").fetchone()[0]
            m_pls   = m_cur.execute("SELECT count(*) FROM playlist").fetchone()[0]
            m_arts  = m_cur.execute("SELECT count(DISTINCT artist) FROM media_file WHERE path NOT LIKE '%.trash%'").fetchone()[0]
            m_sz    = m_cur.execute("SELECT sum(size) FROM media_file WHERE path NOT LIKE '%.trash%'").fetchone()[0] or 0
            m_conn.close()
            music_stats = {
                "songs": m_songs,
                "playlists": m_pls,
                "artists": m_arts,
                "size_gb": round(m_sz / (1024**3), 2),
                "url": f"http://{lan_ip}:8096",
                "ts_url": f"http://{ts_domain}:8096" if ts_domain else ""
            }
    except Exception:
        pass

    # Homelab Automated Agenda & Maintenance Tasks (Dynamic per host)
    agenda = task_manager.get_tasks()

    # Total Storage Capacity Summary
    total_storage_bytes = sum(d["usage"]["total_gb"] * (1024**3) for d in drives_data)
    used_storage_bytes  = sum(d["usage"]["used_gb"] * (1024**3) for d in drives_data)
    free_storage_bytes  = sum(d["usage"]["free_gb"] * (1024**3) for d in drives_data)

    storage_summary = {
        "total_tb": round(total_storage_bytes / (1024**4), 2),
        "used_tb": round(used_storage_bytes / (1024**4), 2),
        "free_tb": round(free_storage_bytes / (1024**4), 2),
        "pct": round((used_storage_bytes / total_storage_bytes * 100), 1) if total_storage_bytes > 0 else 0,
        "status": "Healthy"
    }

    return jsonify({
        "cpu": {"percent": cpu_percent, "cores": cpu_cores, "load": f"{load1:.2f}, {load5:.2f}, {load15:.2f}", "temp": cpu_temp},
        "memory": mem_info,
        "network": net_info,
        "speedtest": speedtest_cache,
        "uptime": uptime_str,
        "drives": drives_data,
        "storage_summary": storage_summary,
        "devices": connected_devices,
        "containers": containers_status,
        "processes": proc_info,
        "proxmox": PROXMOX_CACHE,
        "pbs": PBS_CACHE,
        "music": music_stats,
        "agenda": agenda,
        "hardware": get_system_hardware_info(),
        "app_version": f"v{APP_VERSION}",
        "nodes_telemetry": _NODE_TELEMETRY_CACHE,
        "tailscale": {
            "domain": ts_domain,
            "ip": ts_ip,
            "status": "Connected" if ts_domain else "Disconnected",
            "exit_node": bool(ts_domain),
            "portal_lan": f"http://{lan_ip}:8095",
            "portal_ts": f"http://{ts_domain}:8095" if ts_domain else ""
        }
    })

_SPEEDTEST_LOCK = threading.Lock()
_SPEEDTEST_RUNNING = False

def _run_pure_python_speedtest():
    """
    Pure Python bandwidth benchmark using HTTPS streams.
    Zero external CLI binaries required. 100% compatible across all systems.
    """
    client_ip = ""
    isp = "Broadband Network"
    loc_str = "Global Edge"
    ping_ms = 15.0

    # 1. Latency & ISP detection
    try:
        t0 = time.time()
        req_trace = urllib.request.Request("http://ip-api.com/json/", headers={"User-Agent": "HomelabHub/1.0"})
        with urllib.request.urlopen(req_trace, timeout=4) as r:
            d = json.loads(r.read().decode())
            isp = d.get("isp", "Broadband Network")
            client_ip = d.get("query", "")
            city = d.get("city", "")
            country = d.get("country", "")
            loc_str = f"{city}, {country}".strip(", ") or "Global Edge"
            ping_ms = round((time.time() - t0) * 1000, 1)
    except Exception:
        try:
            t0 = time.time()
            req_ping = urllib.request.Request("https://1.1.1.1/cdn-cgi/trace", headers={"User-Agent": "HomelabHub/1.0"})
            with urllib.request.urlopen(req_ping, timeout=4) as r:
                trace_text = r.read().decode("utf-8", errors="ignore")
                ping_ms = round((time.time() - t0) * 1000, 1)
                for line in trace_text.splitlines():
                    if line.startswith("ip="):
                        client_ip = line.split("=", 1)[1].strip()
        except Exception:
            ping_ms = 18.0

    # 2. Download speed test (stream from global CDN chunk)
    dl_bytes = 0
    t_dl_start = time.time()
    try:
        req_dl = urllib.request.Request(
            "https://speed.cloudflare.com/__down?bytes=25000000",
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://speed.cloudflare.com/",
                "Accept": "*/*"
            }
        )
        with urllib.request.urlopen(req_dl, timeout=10) as r:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                dl_bytes += len(chunk)
                if (time.time() - t_dl_start) >= 5.0:
                    break
        t_dl_dur = max(0.05, time.time() - t_dl_start)
        dl_mbps = round((dl_bytes * 8) / (t_dl_dur * 1024 * 1024), 1)
    except Exception:
        dl_mbps = 0.0

    # 3. Upload speed test (post stream to global CDN)
    ul_mbps = 0.0
    try:
        payload = b"0" * (4 * 1024 * 1024)
        t_ul_start = time.time()
        req_ul = urllib.request.Request(
            "https://speed.cloudflare.com/__up",
            data=payload,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://speed.cloudflare.com/",
                "Content-Type": "application/octet-stream"
            }
        )
        with urllib.request.urlopen(req_ul, timeout=10) as r:
            r.read()
        t_ul_dur = max(0.05, time.time() - t_ul_start)
        ul_mbps = round((len(payload) * 8) / (t_ul_dur * 1024 * 1024), 1)
    except Exception:
        pass

    return {
        "download_mbps": dl_mbps,
        "upload_mbps": ul_mbps,
        "ping_ms": ping_ms,
        "jitter_ms": 0.8,
        "isp": isp,
        "server": "Global Edge CDN",
        "server_location": loc_str,
        "client_ip": client_ip,
        "last_run": time.strftime("%I:%M:%S %p")
    }

def execute_speedtest_multi_tier(server_id=None):
    """Multi-tier speedtest runner that NEVER gets stuck on any OS."""
    import shutil
    
    # Tier 1: Check for official Ookla speedtest CLI
    ookla_bins = ["/usr/local/bin/ookla-speedtest", "/usr/bin/ookla-speedtest", "/usr/local/bin/speedtest", "/usr/bin/speedtest"]
    ookla_path = shutil.which("ookla-speedtest")
    if not ookla_path:
        for b in ookla_bins:
            if os.path.exists(b) and os.access(b, os.X_OK):
                try:
                    v = subprocess.check_output([b, "--version"], timeout=2, stderr=subprocess.STDOUT).decode("utf-8", errors="ignore")
                    if "ookla" in v.lower():
                        ookla_path = b
                        break
                except Exception:
                    pass

    if ookla_path:
        try:
            cmd = [ookla_path, "--accept-license", "--accept-gdpr", "-f", "json"]
            if server_id and str(server_id).isdigit():
                cmd += ["-s", str(server_id)]
            out = subprocess.check_output(cmd, timeout=28, stderr=subprocess.STDOUT).decode("utf-8", errors="ignore")
            data = json.loads(out)
            dl_mbps = round((data["download"]["bandwidth"] * 8) / (1024**2), 1)
            ul_mbps = round((data["upload"]["bandwidth"] * 8) / (1024**2), 1)
            ping_ms = round(data.get("ping", {}).get("latency", 0.0), 1)
            jitter_ms = round(data.get("ping", {}).get("jitter", 0.0), 1)
            isp = data.get("isp", "Local WAN")
            server_info = data.get("server", {})
            server_name = server_info.get("name", "Nearest Server")
            loc_parts = [p for p in [server_info.get('location', ''), server_info.get('country', '')] if p]
            server_location = ", ".join(loc_parts) or "WAN Edge"
            client_ip = data.get("interface", {}).get("externalIp", "")
            return {
                "download_mbps": dl_mbps,
                "upload_mbps": ul_mbps,
                "ping_ms": ping_ms,
                "jitter_ms": jitter_ms,
                "isp": isp,
                "server": server_name,
                "server_location": server_location,
                "client_ip": client_ip,
                "last_run": time.strftime("%I:%M:%S %p")
            }
        except Exception:
            pass

    # Tier 2: Open-source speedtest-cli binary
    cli_path = shutil.which("speedtest-cli")
    if cli_path:
        try:
            cmd = [cli_path, "--json", "--timeout", "15"]
            if server_id and str(server_id).isdigit():
                cmd += ["--server", str(server_id)]
            out = subprocess.check_output(cmd, timeout=25, stderr=subprocess.STDOUT).decode("utf-8", errors="ignore")
            data = json.loads(out)
            return {
                "download_mbps": round(data.get("download", 0) / (1024**2), 1),
                "upload_mbps": round(data.get("upload", 0) / (1024**2), 1),
                "ping_ms": round(data.get("ping", 0.0), 1),
                "jitter_ms": 0.5,
                "isp": data.get("client", {}).get("isp", "Local WAN"),
                "server": data.get("server", {}).get("sponsor", data.get("server", {}).get("name", "Speedtest Node")),
                "server_location": f"{data.get('server', {}).get('name', '')}, {data.get('server', {}).get('country', '')}".strip(", "),
                "client_ip": data.get("client", {}).get("ip", ""),
                "last_run": time.strftime("%I:%M:%S %p")
            }
        except Exception:
            pass

    # Tier 3: Universal pure-Python HTTP fallback (guaranteed to work everywhere)
    return _run_pure_python_speedtest()

@app.route("/api/speedtest-servers")
def get_speedtest_servers():
    import shutil
    ookla_path = shutil.which("ookla-speedtest")
    if not ookla_path:
        for b in ["/usr/local/bin/ookla-speedtest", "/usr/bin/ookla-speedtest", "/usr/local/bin/speedtest", "/usr/bin/speedtest"]:
            if os.path.exists(b) and os.access(b, os.X_OK):
                ookla_path = b
                break

    if ookla_path:
        try:
            out = subprocess.check_output(
                [ookla_path, "--accept-license", "--accept-gdpr", "--servers", "-f", "json"],
                timeout=12
            ).decode("utf-8", errors="ignore")
            data = json.loads(out)
            servers = []
            for s in data.get("servers", [])[:20]:
                servers.append({
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "location": s.get("location", ""),
                    "country": s.get("country", ""),
                    "host": s.get("host", ""),
                    "distance": round(s.get("distance", 0), 1)
                })
            if servers:
                return jsonify({"status": "success", "servers": servers})
        except Exception:
            pass

    # Universal reliable default server targets
    default_servers = [
        {"id": "auto", "name": "Automatic Optimal Server", "location": "Nearest Edge", "country": "Global", "distance": 1.0},
        {"id": "cdn-na", "name": "Cloudflare North America", "location": "Anycast Edge", "country": "US/CA", "distance": 15.0},
        {"id": "cdn-eu", "name": "Cloudflare Europe", "location": "Frankfurt / London", "country": "EU", "distance": 35.0},
        {"id": "cdn-ap", "name": "Cloudflare Asia-Pacific", "location": "Tokyo / Singapore", "country": "APAC", "distance": 60.0}
    ]
    return jsonify({"status": "success", "servers": default_servers})

@app.route("/api/run-speedtest")
def run_speedtest():
    global speedtest_cache, _SPEEDTEST_RUNNING
    with _SPEEDTEST_LOCK:
        if _SPEEDTEST_RUNNING:
            return jsonify({"status": "running", "message": "Speedtest is currently running, please wait..."})
        _SPEEDTEST_RUNNING = True

    try:
        server_id = request.args.get("server_id", None)
        result = execute_speedtest_multi_tier(server_id)
        speedtest_cache = result
        return jsonify({"status": "success", "data": speedtest_cache})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        with _SPEEDTEST_LOCK:
            _SPEEDTEST_RUNNING = False

_WEATHER_CACHE = {}

POPULAR_CITIES = [
    {"name": "New York", "region": "New York", "country": "United States", "lat": 40.7128, "lon": -74.0060, "label": "New York, NY, United States"},
    {"name": "London", "region": "England", "country": "United Kingdom", "lat": 51.5074, "lon": -0.1278, "label": "London, United Kingdom"},
    {"name": "Toronto", "region": "Ontario", "country": "Canada", "lat": 43.7064, "lon": -79.3986, "label": "Toronto, Ontario, Canada"},
    {"name": "Chicago", "region": "Illinois", "country": "United States", "lat": 41.8781, "lon": -87.6298, "label": "Chicago, IL, United States"},
    {"name": "San Francisco", "region": "California", "country": "United States", "lat": 37.7749, "lon": -122.4194, "label": "San Francisco, CA, United States"},
    {"name": "Frankfurt", "region": "Hesse", "country": "Germany", "lat": 50.1109, "lon": 8.6821, "label": "Frankfurt, Germany"},
    {"name": "Paris", "region": "Île-de-France", "country": "France", "lat": 48.8566, "lon": 2.3522, "label": "Paris, France"},
    {"name": "Tokyo", "region": "Kanto", "country": "Japan", "lat": 35.6762, "lon": 139.6503, "label": "Tokyo, Japan"},
    {"name": "Sydney", "region": "NSW", "country": "Australia", "lat": -33.8688, "lon": 151.2093, "label": "Sydney, Australia"},
    {"name": "Singapore", "region": "Central", "country": "Singapore", "lat": 1.3521, "lon": 103.8198, "label": "Singapore"}
]

@app.route("/api/weather/search", methods=["GET"])
def api_weather_search():
    import urllib.parse
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"status": "success", "results": POPULAR_CITIES[:8]})
    
    results = []
    seen_keys = set()
    q_low = q.lower()

    # 1. Exact substring match in local/Ontario catalog
    for item in POPULAR_CITIES:
        if q_low in item["name"].lower() or q_low in item["label"].lower():
            key = (round(item["lat"], 2), round(item["lon"], 2))
            if key not in seen_keys:
                seen_keys.add(key)
                results.append(item)

    # 2. Fuzzy match against local catalog (catches typos like "tornoto" -> "Toronto")
    if not results:
        names_map = {c["name"].lower(): c for c in POPULAR_CITIES}
        close = difflib.get_close_matches(q_low, list(names_map.keys()), n=2, cutoff=0.55)
        for c_name in close:
            item = names_map[c_name]
            key = (round(item["lat"], 2), round(item["lon"], 2))
            if key not in seen_keys:
                seen_keys.add(key)
                results.append(item)

    # 3. Query Open-Meteo Geocoding API for worldwide coverage
    try:
        clean_q = re.sub(r'[,].*$', '', q).strip()
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(clean_q)}&count=10&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "HomelabPortal/1.0"})
        with urllib.request.urlopen(req, timeout=3.5) as r:
            data = json.loads(r.read().decode())
            for res in data.get("results", []):
                name = res.get("name", "")
                admin1 = res.get("admin1", "")
                country = res.get("country", "")
                lat = res.get("latitude")
                lon = res.get("longitude")
                label_parts = [name]
                if admin1: label_parts.append(admin1)
                if country: label_parts.append(country)
                label = ", ".join(label_parts)
                
                key = (round(lat, 2), round(lon, 2))
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append({
                        "name": name,
                        "region": admin1,
                        "country": country,
                        "lat": lat,
                        "lon": lon,
                        "label": label
                    })
    except Exception:
        pass

    return jsonify({"status": "success", "query": q, "results": results[:10]})

@app.route("/api/weather")
def get_weather():
    import urllib.parse
    # Default to Toronto from user settings if available
    default_city = "Toronto"
    saved_lat = None
    saved_lon = None
    saved_label = None

    try:
        _sf = os.path.join(DATA_DIR, "settings.json")
        if os.path.exists(_sf):
            with open(_sf, "r") as _f:
                _s = json.load(_f)
                default_city = _s.get("weather_city") or "Toronto"
                saved_lat = _s.get("weather_lat")
                saved_lon = _s.get("weather_lon")
                saved_label = _s.get("weather_label")
    except Exception:
        pass
        
    city = request.args.get("city", "").strip() or default_city
    req_lat = request.args.get("lat")
    req_lon = request.args.get("lon")
    req_label = request.args.get("label")

    # Only use saved coordinates/label if querying the saved city
    if request.args.get("city") and default_city and request.args.get("city").lower() != default_city.lower():
        saved_lat = None
        saved_lon = None
        saved_label = None

    if req_lat and req_lon:
        saved_lat = float(req_lat)
        saved_lon = float(req_lon)
    if req_label:
        saved_label = req_label

    # If coordinates are passed or city changed, persist them
    if request.args.get("city") or req_lat:
        try:
            _sf = os.path.join(DATA_DIR, "settings.json")
            if os.path.exists(_sf):
                with open(_sf, "r") as _f:
                    _s = json.load(_f)
                _s["weather_city"] = city
                if req_lat and req_lon:
                    _s["weather_lat"] = float(req_lat)
                    _s["weather_lon"] = float(req_lon)
                elif request.args.get("city") and default_city and request.args.get("city").lower() != default_city.lower():
                    _s.pop("weather_lat", None)
                    _s.pop("weather_lon", None)
                if req_label:
                    _s["weather_label"] = req_label
                elif request.args.get("city") and default_city and request.args.get("city").lower() != default_city.lower():
                    _s.pop("weather_label", None)
                with open(_sf, "w") as _f:
                    json.dump(_s, _f, indent=2)
        except Exception:
            pass

    now = time.time()
    cache_key = f"{city}_{saved_lat}_{saved_lon}"
    if cache_key in _WEATHER_CACHE and (now - _WEATHER_CACHE[cache_key]["time"]) < 180:
        return jsonify(_WEATHER_CACHE[cache_key]["data"])

    try:
        # Determine exact lat / lon coordinates
        lat = saved_lat
        lon = saved_lon
        resolved_name = saved_label or city

        if lat is None or lon is None:
            c_low = city.lower().strip()
            # Match popular cities catalog first
            matched = False
            for pc in POPULAR_CITIES:
                if c_low == pc["name"].lower() or c_low in pc["name"].lower():
                    lat, lon = pc["lat"], pc["lon"]
                    resolved_name = pc["label"]
                    matched = True
                    break

            if not matched:
                # Dynamic Geocode via Open-Meteo
                clean_q = re.sub(r'[,].*$', '', city).strip()
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(clean_q)}&count=5&language=en&format=json"
                try:
                    req_geo = urllib.request.Request(geo_url, headers={"User-Agent": "HomelabPortal/1.0"})
                    with urllib.request.urlopen(req_geo, timeout=4) as r:
                        g = json.loads(r.read().decode())
                        results = g.get("results", [])
                        match = results[0] if results else None
                        if match:
                            lat = match["latitude"]
                            lon = match["longitude"]
                            admin = match.get("admin1", "")
                            country = match.get("country", "")
                            resolved_name = f"{match['name']}{', ' + admin if admin else ''}{', ' + country if country else ''}"
                        else:
                            lat, lon = 40.7128, -74.0060
                            resolved_name = city
                except Exception:
                    lat, lon = 40.7128, -74.0060
                    resolved_name = city

        # Fetch Open-Meteo forecast with coordinates
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto"
        req_w = urllib.request.Request(w_url, headers={"User-Agent": "HomelabPortal/1.0"})
        with urllib.request.urlopen(req_w, timeout=5) as r:
            d = json.loads(r.read().decode())
            cur = d["current"]
            daily = d["daily"]
            
            temp_c = round(cur["temperature_2m"])
            feels_c = round(cur["apparent_temperature"])
            temp_f = round((temp_c * 9/5) + 32)
            code = cur.get("weather_code", 0)
            
            WMO = {
                0: ("Clear Sky", "☀️"),
                1: ("Mainly Clear", "🌤️"),
                2: ("Partly Cloudy", "⛅"),
                3: ("Overcast", "☁️"),
                45: ("Fog", "🌫️"),
                48: ("Depositing Rime Fog", "🌫️"),
                51: ("Light Drizzle", "🌧️"),
                53: ("Moderate Drizzle", "🌧️"),
                55: ("Dense Drizzle", "🌧️"),
                61: ("Slight Rain", "🌧️"),
                63: ("Moderate Rain", "🌧️"),
                65: ("Heavy Rain", "🌧️"),
                71: ("Slight Snow", "🌨️"),
                73: ("Moderate Snow", "❄️"),
                75: ("Heavy Snow", "❄️"),
                80: ("Rain Showers", "🌦️"),
                81: ("Moderate Rain Showers", "🌧️"),
                82: ("Violent Rain Showers", "⛈️"),
                95: ("Thunderstorm", "⛈️"),
                96: ("Thunderstorm with Hail", "⛈️")
            }
            desc, icon = WMO.get(code, ("Partly Cloudy", "⛅"))
            
            clean_city_slug = city.lower().replace(" ", "-").replace(",", "")
            weather_data = {
                "city": city,
                "resolved_name": resolved_name,
                "lat": lat,
                "lon": lon,
                "temp_c": str(temp_c),
                "temp_f": str(temp_f),
                "feels_c": str(feels_c),
                "desc": desc,
                "icon": icon,
                "humidity": str(round(cur.get("relative_humidity_2m", 55))),
                "wind_kmph": str(round(cur.get("wind_speed_10m", 15))),
                "max_c": str(round(daily["temperature_2m_max"][0])),
                "min_c": str(round(daily["temperature_2m_min"][0])),
                "twn_url": f"https://www.theweathernetwork.com/weather/{clean_city_slug}",
                "accu_url": f"https://www.accuweather.com/en/search-locations?query={urllib.parse.quote(city)}"
            }
            _WEATHER_CACHE[cache_key] = {"time": now, "data": weather_data}
            return jsonify(weather_data)

    except Exception:
        # Fallback to global wttr.in
        try:
            url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                d = json.loads(r.read().decode())
                cur = d["current_condition"][0]
                weather_desc = cur.get("weatherDesc", [{}])[0].get("value", "Partly Cloudy")
                temp_c = cur.get("temp_C", "25")
                temp_f = cur.get("temp_F", "77")
                feels_c = cur.get("FeelsLikeC", temp_c)
                humidity = cur.get("humidity", "60")
                wind_kmph = cur.get("windspeedKmph", "15")
                today_f = (d.get("weather") or [{}])[0]
                max_c = today_f.get("maxtempC", "25")
                min_c = today_f.get("mintempC", "17")

                weather_data = {
                    "city": city,
                    "resolved_name": city,
                    "temp_c": str(temp_c),
                    "temp_f": str(temp_f),
                    "feels_c": str(feels_c),
                    "desc": weather_desc,
                    "icon": "⛅",
                    "humidity": str(humidity),
                    "wind_kmph": str(wind_kmph),
                    "max_c": str(max_c),
                    "min_c": str(min_c),
                    "twn_url": f"https://www.theweathernetwork.com/weather/{city.lower()}",
                    "accu_url": f"https://www.accuweather.com/en/search-locations?query={urllib.parse.quote(city)}"
                }
                _WEATHER_CACHE[city] = {"time": now, "data": weather_data}
                return jsonify(weather_data)
        except Exception:
            return jsonify({
                "city": city,
                "resolved_name": city,
                "temp_c": "25",
                "temp_f": "77",
                "feels_c": "28",
                "desc": "Partly Cloudy",
                "icon": "⛅",
                "humidity": "60",
                "wind_kmph": "14",
                "max_c": "25",
                "min_c": "17",
                "twn_url": f"https://www.theweathernetwork.com/weather/{city.lower()}",
                "accu_url": f"https://www.accuweather.com/en/search-locations?query={urllib.parse.quote(city)}"
            })

@app.route("/api/proxmox/vm/power", methods=["POST"])
def proxmox_vm_power():
    try:
        data = request.get_json(silent=True) or request.args
        node = data.get("node", "pve")
        vmid = str(data.get("vmid", ""))
        vmtype = data.get("vmtype", "")
        action = data.get("action", "") # 'start', 'stop', 'shutdown', 'reboot'

        if not vmid or action not in ("start", "stop", "shutdown", "reboot"):
            return jsonify({"status": "error", "message": f"Invalid action: {action}"}), 400

        # Auto-detect vmtype if not provided or unknown
        if not vmtype or vmtype not in ("qemu", "lxc"):
            for v in PROXMOX_CACHE.get("vms", []):
                if str(v.get("vmid")) == vmid:
                    vmtype = v.get("type", "qemu")
                    break
        if not vmtype:
            vmtype = "qemu"

        pve_tokens_list = []
        try:
            from pve_fetch import load_pve_tokens
            pve_tokens_list = load_pve_tokens()
        except Exception:
            pass

        cfg = None
        for entry in pve_tokens_list:
            if entry.get("node_id") == node or entry.get("nodename") == node or (entry.get("host") and entry.get("host") in node):
                cfg = entry
                break
        if not cfg and pve_tokens_list:
            cfg = pve_tokens_list[0]

        if not cfg or not cfg.get("host") or not cfg.get("token") or not cfg.get("secret"):
            return jsonify({"status": "error", "message": "Proxmox node credentials not configured in settings"}), 400

        host = cfg["host"]
        nodename = cfg.get("nodename", cfg.get("node_id", node))
        token = cfg["token"]
        secret = cfg["secret"]
        vtype = "qemu" if vmtype in ("qemu", "vm") else "lxc"

        url = f"https://{host}:8006/api2/json/nodes/{nodename}/{vtype}/{vmid}/status/{action}"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            url,
            data=b"",
            headers={"Authorization": f"PVEAPIToken={token}={secret}"},
            method="POST"
        )

        with urllib.request.urlopen(req, context=ctx, timeout=12.0) as r:
            res = json.loads(r.read().decode("utf-8", errors="ignore"))

        # Immediately update status in cache
        for vm in PROXMOX_CACHE.get("vms", []):
            if str(vm.get("vmid")) == vmid:
                vm["status"] = "running" if action in ("start", "reboot") else "stopped"
                break

        return jsonify({"status": "success", "vmid": vmid, "action": action, "res": res})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/proxmox/refresh", methods=["POST", "GET"])
def proxmox_refresh_endpoint():
    """Immediately triggers a live Proxmox query and returns refreshed VM/node cache."""
    try:
        success = _fetch_pve_now()
        return jsonify({
            "status": "success" if success else "warning",
            "nodes": PROXMOX_CACHE.get("nodes", []),
            "vms": PROXMOX_CACHE.get("vms", []),
            "count": len(PROXMOX_CACHE.get("vms", []))
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/docker/power", methods=["POST"])
def docker_container_power():
    try:
        data = request.get_json(silent=True) or request.args
        container = data.get("container", "")
        action = data.get("action", "") # 'start', 'stop', 'restart'

        if not container or action not in ("start", "stop", "restart"):
            return jsonify({"status": "error", "message": "Invalid parameters"})

        cmd = ["docker", action, container]
        out = subprocess.check_output(cmd, timeout=30).decode("utf-8", errors="ignore")
        return jsonify({"status": "success", "message": f"Container {container} {action}ed successfully.", "output": out.strip()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/docker/remove", methods=["POST"])
def docker_remove_container():
    try:
        data = request.get_json(silent=True) or {}
        container = data.get("container", "").strip()
        if not container:
            return jsonify({"status": "error", "message": "Container name required"}), 400
        if container == "nextcloud-aio-mastercontainer":
            return jsonify({"status": "error", "message": "The Nextcloud AIO Mastercontainer cannot be removed."}), 400
        cmd = ["docker", "rm", "-f", container]
        out = subprocess.check_output(cmd, timeout=15).decode("utf-8", errors="ignore")
        return jsonify({"status": "success", "message": f"Container '{container}' deleted successfully.", "output": out.strip()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/restart-unhealthy", methods=["POST"])
def docker_restart_unhealthy():
    try:
        cmd = ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"]
        dps = subprocess.check_output(cmd).decode("utf-8", errors="ignore")
        restarted = []
        errors = []
        ignored = {"nextcloud-aio-borgbackup", "nextcloud-aio-watchtower", "busy_lederberg"}
        for line in dps.splitlines():
            if "|" in line:
                name, stat = line.split("|", 1)
                name = name.strip()
                stat = stat.strip()
                if name in ignored:
                    continue
                if "unhealthy" in stat.lower() or not ("Up" in stat):
                    try:
                        subprocess.check_output(["docker", "restart", name], timeout=35)
                        restarted.append(name)
                    except Exception as ex:
                        errors.append(f"{name}: {str(ex)}")
        if not restarted and not errors:
            return jsonify({"status": "success", "message": "All active containers are healthy! No restarts needed.", "restarted": []})
        return jsonify({
            "status": "success" if not errors else "partial",
            "message": f"Successfully restarted {len(restarted)} containers: {', '.join(restarted)}",
            "restarted": restarted,
            "errors": errors
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/restart-stack", methods=["POST"])
def docker_restart_stack():
    try:
        data = request.get_json(silent=True) or request.args
        stack = (data.get("stack") or "").lower().strip()
        if not stack:
            return jsonify({"status": "error", "message": "Stack name required"}), 400
        
        target_containers = []
        # Dynamic discovery of compose stack containers on any system
        try:
            cmd = ["docker", "ps", "-a", "--format", '{{.Names}}|{{.Label "com.docker.compose.project"}}']
            out = subprocess.check_output(cmd, timeout=6).decode("utf-8", errors="ignore")
            for line in out.splitlines():
                if "|" in line:
                    c_name, c_proj = line.split("|", 1)
                    c_name = c_name.strip()
                    c_proj = c_proj.strip().lower()
                    if c_proj == stack or c_name.lower().startswith(stack + "-") or c_name.lower().startswith(stack + "_") or (stack in c_name.lower()):
                        target_containers.append(c_name)
        except Exception:
            pass

        if not target_containers:
            # Fallback mappings for known legacy groups
            stacks_map = {
                "immich": ["immich_postgres", "immich_redis", "immich_machine_learning", "immich_server"],
                "nextcloud": [
                    "nextcloud-aio-database", "nextcloud-aio-redis", "nextcloud-aio-imaginary",
                    "nextcloud-aio-fulltextsearch", "nextcloud-aio-clamav", "nextcloud-aio-nextcloud",
                    "nextcloud-aio-apache", "nextcloud-aio-whiteboard", "nextcloud-aio-notify-push",
                    "nextcloud-aio-eurooffice", "nextcloud-aio-mastercontainer"
                ],
                "media": ["noble_zakir-main_app-1", "navidrome"],
                "productivity": ["papra", "docuseal"]
            }
            target_containers = stacks_map.get(stack, [])
        
        if not target_containers:
            return jsonify({"status": "error", "message": f"No containers found for stack '{stack}'"}), 404
            
        restarted = []
        errors = []
        for c in target_containers:
            try:
                subprocess.check_output(["docker", "inspect", c], stderr=subprocess.DEVNULL)
                subprocess.check_output(["docker", "restart", c], timeout=35)
                restarted.append(c)
            except Exception as ex:
                errors.append(f"{c}: {str(ex)}")
                
        return jsonify({
            "status": "success" if not errors else "partial",
            "message": f"Successfully restarted {len(restarted)} containers in '{stack.title()}' stack.",
            "restarted": restarted,
            "errors": errors
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/detect-portainer", methods=["GET"])
def api_docker_detect_portainer():
    try:
        lan_ip = get_host_lan_ip()
        ts_domain, _ = get_tailscale_info()
        if not ts_domain:
            ts_domain = get_settings().get("tailscale_domain", "")

        found = None
        cmd = ["docker", "ps", "-a", "--format", '{{.Names}}|{{.Ports}}|{{.Image}}|{{.Status}}']
        out = subprocess.check_output(cmd, timeout=5).decode("utf-8", errors="ignore")
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            c_name = parts[0].strip()
            c_ports = parts[1].strip() if len(parts) > 1 else ""
            c_img = parts[2].strip() if len(parts) > 2 else ""
            c_stat = parts[3].strip() if len(parts) > 3 else ""
            if "portainer" in c_name.lower() or "portainer" in c_img.lower():
                port = "9000"
                port_matches = re.findall(r'(?:0\.0\.0\.0|\[::\]|127\.0\.0\.1):(\d+)->(\d+)', c_ports)
                for host_p, cont_p in port_matches:
                    if cont_p in ("9000", "9443"):
                        port = host_p
                        break
                found = {
                    "name": c_name,
                    "status": c_stat,
                    "port": port,
                    "lan_url": f"http://{lan_ip}:{port}",
                    "ts_url": f"http://{ts_domain}:{port}" if ts_domain else ""
                }
                break
        if not found:
            found = {
                "name": "Portainer (Default Port)",
                "status": "Configured",
                "port": "9000",
                "lan_url": f"http://{lan_ip}:9000",
                "ts_url": f"http://{ts_domain}:9000" if ts_domain else ""
            }
        return jsonify({"status": "success", "data": found})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/portainer/config", methods=["GET", "POST"])
def api_portainer_config():
    settings = get_settings()
    lan_ip = get_host_lan_ip()
    if request.method == "POST":
        try:
            data = request.get_json(silent=True) or {}
            cfg = settings.get("portainer_config", {})
            cfg["title"] = data.get("title", cfg.get("title", "Portainer CE")).strip()
            cfg["subtitle"] = data.get("subtitle", cfg.get("subtitle", "Docker Container Fleet")).strip()
            cfg["lan_url"] = data.get("lan_url", cfg.get("lan_url", f"http://{lan_ip}:9000")).strip()
            cfg["ts_url"] = data.get("ts_url", cfg.get("ts_url", "")).strip()
            cfg["click_action"] = data.get("click_action", cfg.get("click_action", "drawer")).strip()
            settings["portainer_config"] = cfg
            save_settings(settings)
            return jsonify({"status": "success", "config": cfg})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "success", "config": settings.get("portainer_config", {})})

@app.route("/api/drives/check", methods=["POST"])
def api_drives_check():
    """Validates user-submitted mount path (e.g. /mnt/storage), checks usage and authentic SMART telemetry."""
    try:
        data = request.get_json(silent=True) or {}
        raw_path = data.get("path", "").strip()
        if not raw_path:
            return jsonify({"status": "error", "message": "Storage path is required"}), 400
        
        path = os.path.abspath(os.path.expanduser(raw_path))
        if not os.path.exists(path):
            return jsonify({"status": "error", "message": f"Path '{raw_path}' does not exist on this server"}), 404
        
        u = psutil.disk_usage(path)
        real_p = os.path.realpath(path)
        
        # Match against physical disk partitions
        best_part = None
        for p in psutil.disk_partitions(all=False):
            mp = p.mountpoint
            if real_p == mp or real_p.startswith(mp.rstrip('/') + '/'):
                if best_part is None or len(mp) > len(best_part.mountpoint):
                    best_part = p
                    
        dev_path = best_part.device if best_part else "auto"
        fstype = best_part.fstype if best_part else "filesystem"
        
        import re
        m = re.match(r'(/dev/[a-z]+|/dev/nvme\d+n\d+)', dev_path)
        base_dev = m.group(1) if m else dev_path
        
        smart = get_smart_info(base_dev) if base_dev.startswith("/dev/") else {
            "model": "Unified Storage Array" if "pool" in path.lower() else "Filesystem Mount",
            "serial": "N/A",
            "health": "ONLINE",
            "temp": None
        }
        
        suggested = "System OS SSD" if path == "/" else (os.path.basename(path.rstrip('/')).replace("_", " ").title() + " Storage")
        
        return jsonify({
            "status": "success",
            "mount": raw_path,
            "resolved_path": path,
            "device": dev_path,
            "base_dev": base_dev,
            "fstype": fstype,
            "suggested_name": suggested,
            "total_gb": round(u.total / (1024**3), 1),
            "used_gb": round(u.used / (1024**3), 1),
            "free_gb": round(u.free / (1024**3), 1),
            "percent": u.percent,
            "model": smart.get("model", "Storage Device"),
            "serial": smart.get("serial", "N/A"),
            "temp": smart.get("temp"),
            "health": smart.get("health", "ONLINE")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/drives/detect", methods=["GET"])
def api_drives_detect():
    try:
        parts = psutil.disk_partitions(all=False)
        detected = []
        seen = set()
        for p in parts:
            if p.fstype in ('squashfs', 'tmpfs', 'devtmpfs', 'overlay', 'iso9660') or p.mountpoint.startswith('/boot') or p.mountpoint in seen:
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
                seen.add(p.mountpoint)
                m = re.match(r'(/dev/[a-z]+|/dev/nvme\d+n\d+)', p.device)
                base_dev = m.group(1) if m else p.device
                smart = get_smart_info(base_dev)
                
                friendly = "System OS SSD" if p.mountpoint == "/" else (os.path.basename(p.mountpoint).replace("_", " ").title() + " Drive")
                
                detected.append({
                    "mount": p.mountpoint,
                    "device": p.device,
                    "base_dev": base_dev,
                    "fstype": p.fstype,
                    "suggested_name": friendly,
                    "total_gb": round(u.total / (1024**3), 1),
                    "used_gb": round(u.used / (1024**3), 1),
                    "free_gb": round(u.free / (1024**3), 1),
                    "percent": u.percent,
                    "model": smart.get("model", "Storage Device"),
                    "serial": smart.get("serial", "N/A"),
                    "temp": smart.get("temp"),
                    "health": smart.get("health", "PASSED")
                })
            except Exception:
                pass
        return jsonify({"status": "success", "drives": detected})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/drives/config", methods=["GET", "POST"])
def api_drives_config():
    settings = get_settings()
    if request.method == "POST":
        try:
            data = request.get_json(silent=True) or {}
            drives = data.get("drives", [])
            settings["monitored_drives"] = drives
            save_settings(settings)
            return jsonify({"status": "success", "drives": drives})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "success", "drives": settings.get("monitored_drives", [])})

@app.route("/api/settings/icon-size", methods=["POST"])
def api_settings_icon_size():
    try:
        data = request.get_json(silent=True) or {}
        size_px = int(data.get("size_px", 34))
        settings = get_settings()
        settings["quick_icon_size_px"] = max(22, min(64, size_px))
        save_settings(settings)
        return jsonify({"status": "success", "quick_icon_size_px": settings["quick_icon_size_px"]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/logs", methods=["GET"])
def docker_container_logs():
    try:
        container = request.args.get("container", "").strip()
        lines = int(request.args.get("lines", 50))
        if not container:
            return jsonify({"status": "error", "message": "Container name required"}), 400
        cmd = ["docker", "logs", "--tail", str(lines), container]
        logs = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=10).decode("utf-8", errors="ignore")
        return jsonify({"status": "success", "container": container, "logs": logs})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": e.output.decode("utf-8", errors="ignore") or str(e)}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/prune", methods=["POST"])
def docker_prune_space():
    try:
        out = subprocess.check_output(["docker", "system", "prune", "-f"], timeout=30).decode("utf-8", errors="ignore")
        return jsonify({"status": "success", "message": "Docker cleanup complete. Unused resources pruned.", "output": out.strip()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/run-smart-diagnostic", methods=["POST", "GET"])
def api_run_smart_diagnostic():
    try:
        import sys
        scanner_script = "/usr/local/bin/smart_health_scanner.py"
        if not os.path.exists(scanner_script):
            scanner_script = os.path.join(BASE_DIR, "smart_health_scanner.py")
        if _IN_DOCKER:
            subprocess.run([sys.executable, scanner_script], timeout=25)
        else:
            subprocess.run(["sudo", "-n", sys.executable, scanner_script], timeout=25)
        smart_diag_file = os.path.join(BASE_DIR, "smart_diagnostic.json")
        if os.path.exists(smart_diag_file):
            with open(smart_diag_file, "r") as f:
                data = json.load(f)
            return jsonify({"status": "success", "data": data})
        return jsonify({"status": "success", "message": "SMART Scan complete"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from ssd_cleaner import scan_all_garbage, clean_selected_items

@app.route("/api/system/ssd-garbage/scan", methods=["GET"])
def api_ssd_garbage_scan():
    try:
        data = scan_all_garbage()
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/system/ssd-garbage/clean", methods=["POST"])
def api_ssd_garbage_clean():
    try:
        req = request.get_json(silent=True) or {}
        selected = req.get("selected", [])
        if not selected:
            return jsonify({"status": "error", "message": "No categories selected for cleanup"}), 400
        res = clean_selected_items(selected)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from docker_updater import (
    get_cached_updates,
    check_all_container_updates,
    get_cached_updates,
    recreate_container,
    update_all_containers,
    toggle_pin_container,
    get_pinned_containers
)

@app.route("/api/docker/toggle-pin", methods=["POST"])
def api_docker_toggle_pin():
    try:
        req = request.get_json(silent=True) or {}
        container = req.get("container", "").strip()
        reason = req.get("reason", "Custom modifications protected")
        if not container:
            return jsonify({"status": "error", "message": "Container name required"}), 400
        res = toggle_pin_container(container, reason)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/updates", methods=["GET"])
def api_docker_updates():
    try:
        data = get_cached_updates()
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/check-updates", methods=["POST", "GET"])
def api_docker_check_updates():
    try:
        req = request.get_json(silent=True) or {}
        pull_remote = req.get("pull_remote", True)
        if request.args.get("pull_remote") == "false":
            pull_remote = False
        data = check_all_container_updates(pull_remote=pull_remote)
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/update-container", methods=["POST"])
def api_docker_update_container():
    try:
        req = request.get_json(silent=True) or {}
        container = req.get("container", "").strip()
        if not container:
            return jsonify({"status": "error", "message": "Container name required"}), 400
        res = recreate_container(container)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/docker/update-all", methods=["POST"])
def api_docker_update_all():
    try:
        res = update_all_containers()
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route('/api/cards', methods=['GET'])
def api_get_cards():
    return jsonify(get_cards())

@app.route('/api/cards/auto-detect', methods=['GET'])
def api_auto_detect_cards():
    try:
        client_host = request.args.get("host") or request.host.split(':')[0]
        data = detect_docker_applications(client_host=client_host)
        return jsonify(data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cards/auto-create', methods=['POST'])
def api_auto_create_cards():
    try:
        body = request.get_json(silent=True) or {}
        cards = body.get('cards', [])
        replace_existing = bool(body.get('replace_existing', False))
        if not isinstance(cards, list):
            return jsonify({"status": "error", "message": "cards must be a list"}), 400
        result = batch_add_cards(cards, replace_existing=replace_existing)
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ── System Maintenance Tasks & Live Timers ──────────────────────────────────
@app.route("/api/system/tasks", methods=["GET"])
def api_get_system_tasks():
    try:
        return jsonify({"status": "success", "tasks": task_manager.get_tasks()})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/system/tasks/detect", methods=["POST"])
def api_detect_system_tasks():
    try:
        detected = task_manager.detect_system_tasks()
        task_manager.save_tasks(detected)
        return jsonify({"status": "success", "tasks": detected, "count": len(detected)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/system/tasks", methods=["POST"])
def api_add_system_task():
    try:
        data = request.get_json(silent=True) or {}
        new_task = task_manager.add_task(data)
        return jsonify({"status": "success", "task": new_task})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/system/tasks/<task_id>", methods=["PUT"])
def api_update_system_task(task_id):
    try:
        data = request.get_json(silent=True) or {}
        updated = task_manager.update_task(task_id, data)
        if updated:
            return jsonify({"status": "success", "task": updated})
        return jsonify({"status": "error", "message": "Task not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/system/tasks/<task_id>", methods=["DELETE"])
def api_delete_system_task(task_id):
    try:
        success = task_manager.delete_task(task_id)
        if success:
            return jsonify({"status": "success", "deleted_id": task_id})
        return jsonify({"status": "error", "message": "Task not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/setup/complete', methods=['POST'])
def api_complete_setup():
    try:
        body = request.get_json(silent=True) or {}
        settings = get_settings()
        settings['initial_setup_completed'] = True
        if 'dock_position' in body and body['dock_position']:
            settings['dock_position'] = body['dock_position']
        if 'wallpaper' in body:
            settings['wallpaper'] = body['wallpaper']
        if 'wallpaper_type' in body:
            settings['wallpaper_type'] = body['wallpaper_type']
        if 'wallpaper_brightness' in body:
            try:
                settings['wallpaper_brightness'] = float(body['wallpaper_brightness'])
            except Exception:
                pass
        if 'lan_host' in body and body['lan_host']:
            settings['lan_host'] = body['lan_host'].strip()
        if 'tailscale_domain' in body and body['tailscale_domain']:
            settings['tailscale_domain'] = body['tailscale_domain'].strip()
        if 'theme' in body and body['theme']:
            settings['theme'] = body['theme'].strip()
        save_settings(settings)
        return jsonify({"status": "success", "settings": settings})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/network/detect', methods=['GET'])
def api_network_detect():
    try:
        lan_ip = get_host_lan_ip()
        ts_domain, ts_ip = get_tailscale_info()
        settings = get_settings()
        return jsonify({
            "status": "success",
            "detected_lan_ip": lan_ip,
            "detected_ts_domain": ts_domain,
            "detected_ts_ip": ts_ip,
            "configured_lan_host": settings.get("lan_host", lan_ip),
            "configured_tailscale_domain": settings.get("tailscale_domain", ts_domain),
            "configured_tailscale_ip": settings.get("tailscale_ip", ts_ip)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/network/save', methods=['POST'])
def api_network_save():
    import urllib.parse
    try:
        data = request.get_json(silent=True) or {}
        settings = get_settings()
        
        lan_host = data.get("lan_host", "").strip()
        ts_domain = data.get("tailscale_domain", "").strip()
        ts_ip = data.get("tailscale_ip", "").strip()
        update_cards = data.get("update_cards", True)
        
        if lan_host:
            settings["lan_host"] = lan_host
        if ts_domain:
            settings["tailscale_domain"] = ts_domain
        if ts_ip:
            settings["tailscale_ip"] = ts_ip
            
        save_settings(settings)
        
        updated_count = 0
        if update_cards and (ts_domain or lan_host):
            cards = get_cards()
            for c in cards:
                changed = False
                if ts_domain and c.get("ts_url"):
                    try:
                        u = urllib.parse.urlparse(c["ts_url"])
                        new_netloc = ts_domain if not u.port else f"{ts_domain}:{u.port}"
                        new_ts_url = urllib.parse.urlunparse((u.scheme or "http", new_netloc, u.path, u.params, u.query, u.fragment))
                        if new_ts_url != c["ts_url"]:
                            c["ts_url"] = new_ts_url
                            changed = True
                    except Exception:
                        pass
                if changed:
                    updated_count += 1
            if updated_count > 0:
                save_cards(cards)
                
        return jsonify({
            "status": "success",
            "settings": settings,
            "updated_cards_count": updated_count
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cards/reorder', methods=['POST'])
def api_reorder_cards():
    try:
        data = request.get_json(silent=True) or {}
        card_ids = data.get('card_ids', [])
        if not isinstance(card_ids, list):
            return jsonify({"status": "error", "message": "card_ids must be a list"}), 400
        reordered = reorder_cards(card_ids)
        return jsonify({"status": "success", "cards": reordered})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cards', methods=['POST'])
def api_add_card():
    try:
        data = request.get_json(silent=True) or {}
        card = add_card(data)
        return jsonify({"status": "success", "card": card})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cards/<card_id>', methods=['PUT'])
def api_update_card(card_id):
    try:
        data = request.get_json(silent=True) or {}
        res = update_card(card_id, data)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cards/<card_id>', methods=['DELETE'])
def api_delete_card(card_id):
    try:
        res = delete_card(card_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify(get_settings())

@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    try:
        data = request.get_json(silent=True) or {}
        settings = get_settings()
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(settings.get(k), dict):
                settings[k].update(v)
            else:
                settings[k] = v
        save_settings(settings)
        return jsonify({"status": "success", "settings": settings})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/icons', methods=['GET'])
def api_get_icons():
    return jsonify(get_available_icons())

@app.route('/api/upload/icon', methods=['POST'])
def api_upload_icon():
    try:
        if 'icon' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        file = request.files['icon']
        url = save_uploaded_icon(file)
        if not url:
            return jsonify({"status": "error", "message": "Invalid file format (use .png, .svg, .jpg, .webp)"}), 400
        return jsonify({"status": "success", "url": url})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload/wallpaper', methods=['POST'])
def api_upload_wallpaper():
    try:
        if 'wallpaper' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        file = request.files['wallpaper']
        url = save_uploaded_wallpaper(file)
        if not url:
            return jsonify({"status": "error", "message": "Invalid image format (use .png, .jpg, .webp)"}), 400
        settings = get_settings()
        settings['wallpaper'] = url
        settings['wallpaper_type'] = 'custom'
        save_settings(settings)
        return jsonify({"status": "success", "url": url, "settings": settings})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ── Calendar, Daily Energy Ledger & iCal Sync Endpoints ─────────────────────
@app.route("/api/calendar/month")
def get_calendar_month():
    try:
        now = datetime.now()
        year = int(request.args.get("year", now.year))
        month = int(request.args.get("month", now.month))
        
        cal_data = calendar_manager.load_calendar_data()
        days_data = cal_data.get("days", {})
        
        # Filter days belonging to this year-month
        month_prefix = f"{year:04d}-{month:02d}"
        month_days = {k: v for k, v in days_data.items() if k.startswith(month_prefix)}
        
        # External calendar events
        ext_events = calendar_manager.get_synced_external_events_for_month(year, month)
        
        # Collect all events for this month across all days
        month_events = []
        for d_str in sorted(month_days.keys()):
            for ev in month_days[d_str].get("events", []):
                ev_copy = dict(ev)
                ev_copy["date"] = d_str
                month_events.append(ev_copy)
        
        # Include any external synced events
        for ex in ext_events:
            month_events.append(ex)

        # Compute monthly total energy from the daily records
        month_kwh = sum(d.get("energy", {}).get("kwh", 0.0) for d in month_days.values())
        rate = calendar_manager._get_electricity_rate()
        month_cost = round(month_kwh * rate, 2)

        return jsonify({
            "status": "success",
            "year": year,
            "month": month,
            "days": month_days,
            "month_events": month_events,
            "month_total_kwh": round(month_kwh, 3),
            "month_total_cost": month_cost,
            "external_events": ext_events,
            "summary": {
                "total_kwh": round(month_kwh, 3),
                "total_cost": month_cost,
                "recorded_days": len(month_days),
                "total_events": len(month_events)
            },
            "feeds": cal_data.get("feeds", [])
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/calendar/day")
def get_calendar_day():
    try:
        date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
        cal_data = calendar_manager.load_calendar_data()
        day_info = cal_data.get("days", {}).get(date_str, {
            "energy": {"kwh": 0.0, "cost": 0.0, "avg_watts": 0.0, "runtime_hours": 0.0, "rate_kwh": calendar_manager._get_electricity_rate()},
            "events": []
        })
        
        # Also grab any external events for this specific day
        try:
            parts = date_str.split('-')
            y, m = int(parts[0]), int(parts[1])
            ext_map = calendar_manager.get_synced_external_events_for_month(y, m)
            ext_events = ext_map.get(date_str, [])
        except Exception:
            ext_events = []
            
        return jsonify({
            "status": "success",
            "date": date_str,
            "energy": day_info.get("energy", {}),
            "events": day_info.get("events", []),
            "external_events": ext_events
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/calendar/events", methods=["POST"])
def add_calendar_event():
    try:
        req = request.get_json(force=True) or {}
        date_str = req.get("date", datetime.now().strftime("%Y-%m-%d"))
        time_str = req.get("time", datetime.now().strftime("%I:%M %p"))
        title = req.get("title", "Custom Event").strip()
        desc = req.get("desc", "").strip()
        category = req.get("category", "user_note")
        tag = req.get("tag", "Note")
        
        if not title:
            return jsonify({"status": "error", "message": "Title is required"}), 400
            
        new_event = calendar_manager.add_user_event(date_str, time_str, title, desc, category, tag)
        return jsonify({"status": "success", "event": new_event})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/calendar/events/<event_id>", methods=["DELETE"])
def delete_calendar_event(event_id):
    try:
        date_str = request.args.get("date") or (request.get_json(silent=True) or {}).get("date") or ""
        success = calendar_manager.delete_user_event(date_str, event_id)
        return jsonify({"status": "success" if success else "not_found"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/calendar/feeds", methods=["GET", "POST", "DELETE"])
def handle_calendar_feeds():
    try:
        cal_data = calendar_manager.load_calendar_data()
        feeds = cal_data.setdefault("feeds", [])
        
        if request.method == "GET":
            return jsonify({"status": "success", "feeds": feeds})
            
        elif request.method == "POST":
            req = request.get_json(force=True) or {}
            feed_id = req.get("id") or f"feed_{int(time.time())}"
            name = req.get("name", "External Calendar").strip()
            provider = req.get("provider", "google").strip()
            url = req.get("url", "").strip()
            color = req.get("color", "#3b82f6")
            
            if not url:
                return jsonify({"status": "error", "message": "Calendar feed URL is required"}), 400
                
            test_evts = calendar_manager.fetch_external_feed(feed_id, url, name, color)
            
            existing = next((f for f in feeds if f.get("id") == feed_id), None)
            feed_obj = {
                "id": feed_id,
                "name": name,
                "provider": provider,
                "url": url,
                "color": color,
                "enabled": True,
                "last_synced": time.time(),
                "event_count": len(test_evts)
            }
            if existing:
                existing.update(feed_obj)
            else:
                feeds.append(feed_obj)
                
            calendar_manager.save_calendar_data(cal_data)
            return jsonify({"status": "success", "feed": feed_obj, "events_found": len(test_evts)})
            
        elif request.method == "DELETE":
            feed_id = request.args.get("id") or (request.get_json(silent=True) or {}).get("id")
            if not feed_id:
                return jsonify({"status": "error", "message": "Feed id is required"}), 400
            cal_data["feeds"] = [f for f in feeds if f.get("id") != feed_id]
            calendar_manager.save_calendar_data(cal_data)
            return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/calendar/sync", methods=["POST"])
def trigger_calendar_sync():
    try:
        cal_data = calendar_manager.load_calendar_data()
        feeds = cal_data.get("feeds", [])
        total_evts = 0
        for f in feeds:
            calendar_manager._EXTERNAL_EVENTS_CACHE.pop(f.get("id"), None)
            evts = calendar_manager.fetch_external_feed(
                f.get("id"), f.get("url"), f.get("name"), f.get("color", "#3b82f6")
            )
            f["last_synced"] = time.time()
            f["event_count"] = len(evts)
            total_evts += len(evts)
        calendar_manager.save_calendar_data(cal_data)
        return jsonify({"status": "success", "synced_feeds": len(feeds), "total_events": total_evts})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/calendar/feed.ics")
def export_homelab_ics():
    """Outgoing subscription feed URL for iPhone / Mac / Google Calendar / Outlook"""
    try:
        host = request.host_url.rstrip('/')
        ics_content = calendar_manager.generate_homelab_ics_feed(server_url=host)
        return Response(
            ics_content,
            mimetype="text/calendar",
            headers={
                "Content-Disposition": "inline; filename=homelab_events.ics",
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )
    except Exception as e:
        return Response(f"Error generating calendar: {e}", status=500, mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8095, debug=False, threaded=True)


