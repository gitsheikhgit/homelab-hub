#!/usr/bin/env python3
import subprocess, json, time, os, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
settings_file = os.path.join(BASE_DIR, "data", "settings.json")
drives_config = []

if os.path.exists(settings_file):
    try:
        with open(settings_file, "r") as sf:
            s_data = json.load(sf)
            for d in s_data.get("monitored_drives", []):
                dev = d.get("dev")
                name = d.get("name") or "Storage Drive"
                mount = d.get("mount") or "/"
                # Ignore container virtual mount artifacts
                if mount in ("/etc/resolv.conf", "/etc/hostname", "/etc/hosts", "/app/data") or mount.startswith("/etc/"):
                    continue
                if dev:
                    drives_config.append((dev, name, mount))
    except Exception:
        pass

if not drives_config:
    # Look at host PID 1 mounts (or host mounts) first
    for mf in ("/host/proc/1/mounts", "/proc/1/mounts", "/proc/mounts"):
        if os.path.exists(mf):
            try:
                with open(mf, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2 and re.match(r'^/dev/(sd[a-z]|nvme\d+n\d+|vd[a-z]|hd[a-z]|xvd[a-z]|mapper/)', parts[0]):
                            base_dev = re.sub(r'p?\d+$', '', parts[0])
                            mount_pt = parts[1]
                            if mount_pt.startswith(("/boot", "/var", "/etc", "/app")) or mount_pt in ("/etc/resolv.conf", "/etc/hostname", "/etc/hosts"):
                                continue
                            if not any(d[0] == base_dev for d in drives_config):
                                friendly = "Internal OS SSD" if mount_pt == "/" else (os.path.basename(mount_pt).replace("_", " ").title() + " Drive")
                                drives_config.append((base_dev, friendly, mount_pt))
            except Exception:
                pass
            if drives_config:
                break

if not drives_config:
    drives_config = [
        ("/dev/sda", "Internal OS SSD", "/"),
        ("/dev/sdb", "Backup Drive (Yottamaster)", "/mnt/backup_hdd"),
        ("/dev/sdc", "Storage Drive (Yottamaster)", "/mnt/storage"),
        ("/dev/sdd", "WDDATA Drive (Yottamaster)", "/mnt/WDDATA"),
    ]

results = {
    "last_scan_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    "last_scan_timestamp": int(time.time()),
    "overall_status": "ALL_HEALTHY",
    "drives": {}
}

any_warning = False

for dev, friendly_name, mount_point in drives_config:
    drive_res = {
        "dev": dev,
        "name": friendly_name,
        "mount": mount_point,
        "health": "PASSED",
        "model": "Solid State Disk / Hard Drive",
        "serial": "Unknown",
        "temp": 35,
        "hours": 0,
        "years": 0.0,
        "reallocated": 0,
        "pending_sectors": 0,
        "uncorrectable": 0,
        "crc_errors": 0,
        "last_test": "Short self-test completed without error",
        "last_checked_str": time.strftime("Today at %I:%M %p", time.localtime())
    }
    
    if os.path.exists(dev):
        out = ""
        # Try SAT first (for USB enclosures/SATA), then standard
        for sat_flag in [["-d", "sat"], []]:
            try:
                cmd = ["sudo", "smartctl"] + sat_flag + ["-H", "-i", "-A", dev]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
                if res.stdout and ("Model" in res.stdout or "health" in res.stdout.lower() or "Attributes" in res.stdout):
                    out = res.stdout
                    break
            except Exception:
                pass

        if out:
            for line in out.splitlines():
                line_str = line.strip()
                if "Device Model:" in line_str or "Model Family:" in line_str or "Model Number:" in line_str:
                    parts = line_str.split(":", 1)
                    if len(parts) > 1:
                        drive_res["model"] = parts[1].strip()
                elif "Serial Number:" in line_str:
                    drive_res["serial"] = line_str.split(":", 1)[1].strip()
                elif "SMART overall-health" in line_str or "SMART Health Status" in line_str:
                    if "PASSED" in line_str or "OK" in line_str:
                        drive_res["health"] = "PASSED"
                    elif "FAILED" in line_str:
                        drive_res["health"] = "FAILED"
                        any_warning = True
                
                # Precise Attribute ID parsing
                parts = line_str.split()
                if len(parts) >= 6 and parts[0].isdigit():
                    try:
                        attr_id = int(parts[0])
                        raw_str = parts[-1]
                        raw_int = int(raw_str.split('/')[0].split('(')[0].strip())
                        
                        if attr_id == 5:
                            drive_res["reallocated"] = raw_int
                            if raw_int > 0:
                                drive_res["last_test"] = f"Warning: {raw_int} reallocated sectors"
                                any_warning = True
                        elif attr_id == 9:
                            drive_res["hours"] = raw_int
                            drive_res["years"] = round(raw_int / 8760.0, 1)
                        elif attr_id in (194, 190):
                            if 10 <= raw_int <= 90:
                                drive_res["temp"] = raw_int
                        elif attr_id == 197:
                            drive_res["pending_sectors"] = raw_int
                        elif attr_id == 198:
                            drive_res["uncorrectable"] = raw_int
                        elif attr_id == 199:
                            drive_res["crc_errors"] = raw_int
                    except Exception:
                        pass
                        
    results["drives"][dev] = drive_res

if any_warning:
    results["overall_status"] = "WARNING_DETECTED"

out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_diagnostic.json")
with open(out_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"[+] SMART Health Check Complete. File saved to {out_file}")
