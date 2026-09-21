#!/usr/bin/env python3
"""Standalone Proxmox poller - runs as subprocess, prints JSON to stdout."""
import urllib.request
import urllib.parse
import ssl
import json
import os
import time
import re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def load_pve_tokens():
    """Load Proxmox API tokens dynamically from env var or data/settings.json."""
    env_tokens = os.environ.get("PROXMOX_TOKENS")
    if env_tokens:
        try:
            parsed = json.loads(env_tokens)
            if isinstance(parsed, list) and parsed:
                return parsed
        except Exception:
            pass

    settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                s = json.load(f)
                toks = s.get("proxmox_tokens") or []
                if toks and isinstance(toks, list) and len(toks) > 0:
                    return toks
                # Fallback: check if cluster_nodes has proxmox credentials embedded
                cluster_nodes = s.get("cluster_nodes") or []
                derived = []
                for n in cluster_nodes:
                    if n.get("type") == "proxmox":
                        host = n.get("ip") or (n.get("url", "").replace("https://", "").replace("http://", "").split("/")[0].split(":")[0])
                        if host and (n.get("token") or n.get("password") or n.get("secret")):
                            derived.append({
                                "host": host,
                                "node_id": n.get("id", "pve"),
                                "nodename": n.get("nodename") or "pve",
                                "token": n.get("token", ""),
                                "secret": n.get("secret", ""),
                                "username": n.get("username", "root@pam"),
                                "password": n.get("password", "")
                            })
                if derived:
                    return derived
        except Exception:
            pass

    return []

PVE_TOKENS = load_pve_tokens()

_TICKETS = {}

def get_pve_auth_headers(entry):
    """Return either PVEAPIToken or PVEAuthCookie (username/password ticket)."""
    token = entry.get("token", "")
    secret = entry.get("secret", "")
    if token and secret:
        return {"Authorization": f"PVEAPIToken={token}={secret}"}

    host = entry.get("host")
    username = entry.get("username")
    password = entry.get("password")
    if host and username and password:
        now = time.time()
        cached = _TICKETS.get(host)
        if cached and (now - cached.get("time", 0)) < 3600:
            return {"Cookie": f"PVEAuthCookie={cached.get('ticket')}"}
        try:
            t_url = f"https://{host}:8006/api2/json/access/ticket"
            post_data = urllib.parse.urlencode({"username": username, "password": password}).encode("utf-8")
            t_req = urllib.request.Request(t_url, data=post_data, method="POST")
            with urllib.request.urlopen(t_req, context=ctx, timeout=5.0) as r:
                body = json.loads(r.read().decode())
                ticket = body.get("data", {}).get("ticket")
                if ticket:
                    _TICKETS[host] = {"ticket": ticket, "time": now}
                    return {"Cookie": f"PVEAuthCookie={ticket}"}
        except Exception as e:
            pass
    return {}

def pve_get(entry, path):
    host = entry.get("host")
    headers = get_pve_auth_headers(entry)
    if not headers:
        return []
    url = f"https://{host}:8006/api2/json{path}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=5.0) as r:
        return json.loads(r.read().decode()).get("data", [])

def get_arp_map():
    """Build MAC -> IP lookup dictionary from host ARP table."""
    arp = {}
    try:
        if os.path.exists("/proc/net/arp"):
            with open("/proc/net/arp", "r") as f:
                for line in f.readlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        ip, mac = parts[0], parts[3].lower()
                        if mac != "00:00:00:00:00:00":
                            arp[mac] = ip
    except Exception:
        pass
    return arp

_ARP_CACHE = None

def get_ip(entry, vmtype, vmid, nodename):
    """Try to get primary IP for a VM/LXC using Guest Agent + ARP MAC fallback."""
    global _ARP_CACHE
    try:
        if vmtype == "lxc":
            ifaces = pve_get(entry, f"/nodes/{nodename}/lxc/{vmid}/interfaces")
            for iface in ifaces:
                for key in ("inet", "inet6"):
                    val = iface.get(key, "")
                    if val and not val.startswith("127.") and not val.startswith("::1") and not val.startswith("fe80"):
                        return val.split("/")[0]
        elif vmtype == "qemu":
            # 1. Try QEMU Guest Agent first
            try:
                ifaces = pve_get(entry, f"/nodes/{nodename}/qemu/{vmid}/agent/network-get-interfaces")
                if isinstance(ifaces, dict):
                    ifaces = ifaces.get("result", [])
                for iface in ifaces:
                    iname = iface.get("name", "")
                    if iname != "lo" and not iname.startswith("loop"):
                        for ip_entry in iface.get("ip-addresses", []):
                            ip_val = ip_entry.get("ip-address", "")
                            if ip_entry.get("ip-address-type") == "ipv4" and not ip_val.startswith("127.") and not ip_val.startswith("169.254"):
                                return ip_val
            except Exception:
                pass

            # 2. Fallback: Lookup VM MAC address in host ARP table
            try:
                cfg = pve_get(entry, f"/nodes/{nodename}/qemu/{vmid}/config")
                if isinstance(cfg, dict):
                    for k, v in cfg.items():
                        if k.startswith("net") and isinstance(v, str):
                            match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', v)
                            if match:
                                mac = match.group(0).lower()
                                if _ARP_CACHE is None:
                                    _ARP_CACHE = get_arp_map()
                                if mac in _ARP_CACHE:
                                    return _ARP_CACHE[mac]
            except Exception:
                pass
    except Exception:
        pass
    return "--"

result = {"nodes": [], "vms": [], "pbs": {}}

for entry in PVE_TOKENS:
    host      = entry.get("host")
    node_id   = entry.get("node_id", "pve")
    nodename  = entry.get("nodename", "pve")

    # ── 1. Get cluster resources ──────────────────────────────────────────
    try:
        resources = pve_get(entry, "/cluster/resources")
    except Exception as e:
        result["nodes"].append({"id": node_id, "error": str(e)})
        continue

    # ── 2. Extract node stats (fall back to /nodes/{name}/status if zeroed) ──
    node_entry = next((r for r in resources if r.get("type") == "node" and (r.get("node") == nodename or not nodename)), None)
    if not node_entry:
        node_entry = next((r for r in resources if r.get("type") == "node"), None)

    cpu_usage, ram_usage, maxcpu = 0.0, "N/A", 0
    if node_entry and node_entry.get("maxcpu", 0) > 0:
        maxmem = node_entry.get("maxmem", 1)
        mem    = node_entry.get("mem", 0)
        cpu_usage = round(node_entry.get("cpu", 0) * 100, 1)
        ram_usage = f"{round(mem/1e9,2)} GB / {round(maxmem/1e9,2)} GB"
        maxcpu    = node_entry.get("maxcpu", 0)
    else:
        # Fallback: query /nodes/{nodename}/status directly
        try:
            ns = pve_get(entry, f"/nodes/{nodename}/status")
            if isinstance(ns, dict):
                maxmem = ns.get("memory", {}).get("total", 1)
                mem    = ns.get("memory", {}).get("used", 0)
                maxcpu = ns.get("cpuinfo", {}).get("cpus", 0)
                cpu_usage = round(ns.get("cpu", 0) * 100, 1)
                ram_usage = f"{round(mem/1e9,2)} GB / {round(maxmem/1e9,2)} GB"
        except Exception:
            pass

    # Count online VMs for this specific node
    node_vms = [r for r in resources if r.get("type") in ("qemu", "lxc") and (r.get("node") == nodename or not nodename)]
    online_count = sum(1 for v in node_vms if v.get("status") == "running")
    total_count = len(node_vms)

    result["nodes"].append({
        "id":         node_id,
        "name":       nodename,
        "cpu_usage":  cpu_usage,
        "ram_usage":  ram_usage,
        "maxcpu":     maxcpu,
        "online_vms": online_count,
        "vms_count":  total_count
    })

    # ── 3. PBS storage ────────────────────────────────────────────────────
    if not result["pbs"]:
        pbs_item = next((r for r in resources
                         if r.get("type") == "storage" and r.get("plugintype") == "pbs"), None)
        if pbs_item:
            used  = pbs_item.get("disk", 0)
            total = pbs_item.get("maxdisk", 1)
            free  = total - used
            pct   = round(used / total * 100, 1) if total > 0 else 0
            result["pbs"] = {
                "datastore": "pbs-node1",
                "used_str":  f"{round(used/1e9, 1)} GB",
                "total_str": f"{round(total/1e9, 1)} GB",
                "free_str":  f"{round(free/1e9, 1)} GB",
                "pct":       pct,
                "status":    pbs_item.get("status", "unknown"),
            }

    # ── 4. VMs from cluster/resources ────────────────────────────────────
    cluster_vms = [r for r in resources if r.get("type") in ("qemu", "lxc")]

    if cluster_vms:
        for item in cluster_vms:
            vtype  = item.get("type")
            vmid   = item.get("vmid")
            status = item.get("status", "stopped")
            ip = get_ip(entry, vtype, vmid, nodename) if status == "running" else "--"
            result["vms"].append({
                "vmid":    vmid,
                "name":    item.get("name", f"vm-{vmid}"),
                "node":    node_id,
                "host":    host,
                "type":    vtype,
                "status":  status,
                "cpus":    item.get("maxcpu", 1),
                "ram":     f"{round(item.get('maxmem',0)/1e9,1)} GB",
                "cpu_pct": round(item.get("cpu", 0) * 100, 1),
                "ip":      ip,
            })
    else:
        # Fallback: query qemu and lxc endpoints directly
        for vmtype, endpoint in [("qemu", f"/nodes/{nodename}/qemu"), ("lxc", f"/nodes/{nodename}/lxc")]:
            try:
                vms = pve_get(entry, endpoint)
                for item in vms:
                    vmid   = item.get("vmid")
                    status = item.get("status", "stopped")
                    ip = get_ip(entry, vmtype, vmid, nodename) if status == "running" else "--"
                    result["vms"].append({
                        "vmid":    vmid,
                        "name":    item.get("name", f"vm-{vmid}"),
                        "node":    node_id,
                        "host":    host,
                        "type":    vmtype,
                        "status":  status,
                        "cpus":    item.get("maxcpu", item.get("cpus", 1)),
                        "ram":     f"{round(item.get('maxmem',0)/1e9,1)} GB",
                        "cpu_pct": round(item.get("cpu", 0) * 100, 1),
                        "ip":      ip,
                    })
            except Exception:
                pass

print(json.dumps(result))
