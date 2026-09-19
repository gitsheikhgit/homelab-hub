#!/usr/bin/env python3
"""
calendar_manager.py - Homelab Calendar, Daily Energy Ledger & External iCal Sync Engine
Features:
- Rolling 90-day (1-3 months) persistent daily energy & event ledger
- Automatic tracking of Proxmox PBS backups, Docker updates, SSD trims, and system milestones
- Two-way iCal support:
  1. Parse & sync external iCal feeds (Google Calendar, Apple iCloud, Microsoft Outlook, Nextcloud)
  2. Generate outgoing .ics subscription feed (/api/calendar/feed.ics) for iPhone / Mac / Google Calendar
- Pure Python standard library implementation (zero fragile external dependencies)
"""

import os
import json
import time
import re
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CALENDAR_FILE = os.path.join(DATA_DIR, 'calendar_events.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

RETENTION_DAYS = 90  # 3-month rolling window

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_calendar_data():
    _ensure_data_dir()
    if not os.path.exists(CALENDAR_FILE):
        data = _generate_initial_data()
        save_calendar_data(data)
        return data
    try:
        with open(CALENDAR_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not isinstance(data, dict):
                data = _generate_initial_data()
            if "days" not in data:
                data["days"] = {}
            if "feeds" not in data:
                data["feeds"] = []
            return data
    except Exception as e:
        print(f"[CalendarManager] Error loading calendar data: {e}")
        return _generate_initial_data()

def save_calendar_data(data):
    _ensure_data_dir()
    try:
        # Prune records older than RETENTION_DAYS
        cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
        if "days" in data and isinstance(data["days"], dict):
            pruned_days = {k: v for k, v in data["days"].items() if k >= cutoff}
            data["days"] = pruned_days

        with open(CALENDAR_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"[CalendarManager] Error saving calendar data: {e}")
        return False

def _get_electricity_rate():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                s = json.load(f)
                val = s.get("elec_rate_kwh")
                if val is not None and float(val) > 0:
                    return float(val)
    except Exception:
        pass
    return 0.23  # default $/kWh

def _generate_initial_data():
    """Initialize clean calendar ledger for fresh installations."""
    now_str = datetime.now().strftime("%Y-%m-%d")
    rate = _get_electricity_rate()
    days = {
        now_str: {
            "energy": {
                "kwh": 0.0,
                "cost": 0.0,
                "avg_watts": 0.0,
                "runtime_hours": 0.0,
                "rate_kwh": rate
            },
            "events": []
        }
    }
    return {
        "days": days,
        "feeds": [],
        "last_sync": time.time()
    }

def record_daily_energy(date_str, added_kwh, current_watts, rate_kwh):
    """Called continuously by update_energy_tracker in app.py"""
    data = load_calendar_data()
    days = data.setdefault("days", {})
    
    day_rec = days.setdefault(date_str, {
        "energy": {
            "kwh": 0.0,
            "cost": 0.0,
            "avg_watts": current_watts,
            "runtime_hours": 0.0,
            "rate_kwh": rate_kwh
        },
        "events": []
    })
    
    eng = day_rec.setdefault("energy", {})
    eng["kwh"] = round(eng.get("kwh", 0.0) + added_kwh, 4)
    eng["cost"] = round(eng["kwh"] * rate_kwh, 3)
    eng["rate_kwh"] = rate_kwh
    
    # Smooth moving average watts
    prev_w = eng.get("avg_watts", current_watts)
    eng["avg_watts"] = round((prev_w * 0.95) + (current_watts * 0.05), 1)
    
    save_calendar_data(data)

def log_system_event(title, desc, category="system", tag="Homelab", badge_color=None):
    """Log an operational event into today's calendar ledger"""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M %p")
    
    if not badge_color:
        colors = {
            "backup": "var(--accent-green)",
            "docker": "var(--accent-blue)",
            "storage": "var(--accent-cyan)",
            "system": "var(--accent-proxmox)",
            "user_note": "#a855f7"
        }
        badge_color = colors.get(category, "var(--accent-blue)")
        
    data = load_calendar_data()
    days = data.setdefault("days", {})
    day_rec = days.setdefault(date_str, {
        "energy": {"kwh": 0.0, "cost": 0.0, "avg_watts": 17.5, "runtime_hours": 0.0, "rate_kwh": 0.23},
        "events": []
    })
    
    event_id = f"evt_{int(time.time())}_{len(day_rec.setdefault('events', []))}"
    day_rec["events"].append({
        "id": event_id,
        "time": time_str,
        "title": title,
        "desc": desc,
        "category": category,
        "tag": tag,
        "badge_color": badge_color,
        "source": "system"
    })
    
    save_calendar_data(data)
    return event_id

def add_user_event(date_str, time_str, title, desc, category="user_note", tag="Note"):
    """User adds a maintenance note or personal event from the UI"""
    data = load_calendar_data()
    days = data.setdefault("days", {})
    rate = _get_electricity_rate()
    day_rec = days.setdefault(date_str, {
        "energy": {"kwh": 0.0, "cost": 0.0, "avg_watts": 0.0, "runtime_hours": 0.0, "rate_kwh": rate},
        "events": []
    })
    
    badge_colors = {
        "user_note": "#a855f7",
        "maintenance": "#f59e0b",
        "backup": "var(--accent-green)",
        "docker": "var(--accent-blue)",
        "system": "var(--accent-proxmox)"
    }
    badge_color = badge_colors.get(category, "#a855f7")
    
    event_id = f"evt_usr_{int(time.time())}"
    new_event = {
        "id": event_id,
        "time": time_str or datetime.now().strftime("%I:%M %p"),
        "title": title,
        "desc": desc,
        "category": category,
        "tag": tag,
        "badge_color": badge_color,
        "source": "user_note"
    }
    day_rec.setdefault("events", []).append(new_event)
    save_calendar_data(data)
    return new_event

def delete_user_event(date_str, event_id):
    """Delete a user-created event"""
    data = load_calendar_data()
    days = data.get("days", {})
    if date_str and date_str in days and "events" in days[date_str]:
        orig_len = len(days[date_str]["events"])
        days[date_str]["events"] = [e for e in days[date_str]["events"] if e.get("id") != event_id]
        if len(days[date_str]["events"]) < orig_len:
            save_calendar_data(data)
            return True
    else:
        for d, day_info in days.items():
            evs = day_info.get("events", [])
            for e in evs:
                if e.get("id") == event_id:
                    day_info["events"] = [x for x in evs if x.get("id") != event_id]
                    save_calendar_data(data)
                    return True
    return False

# ── External iCal / Webcal Parsing & Sync Engine ───────────────────────────
_EXTERNAL_EVENTS_CACHE = {}  # {feed_id: {"events": [...], "time": timestamp}}

def parse_ics_feed(ics_content, provider_name="External", provider_color="#3b82f6"):
    """
    Pure Python RFC 5545 iCalendar (.ics) parser.
    Supports Google Calendar, Apple iCloud, Outlook, and Nextcloud.
    """
    events = []
    lines = ics_content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    
    # Unfold long lines (RFC 5545 line continuation starts with space or tab)
    unfolded = []
    for line in lines:
        if line.startswith(' ') or line.startswith('\t'):
            if unfolded:
                unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
            
    in_event = False
    current_evt = {}
    
    for line in unfolded:
        line_s = line.strip()
        if line_s == "BEGIN:VEVENT":
            in_event = True
            current_evt = {}
        elif line_s == "END:VEVENT" and in_event:
            in_event = False
            # Normalize date and summary
            summary = current_evt.get("SUMMARY", "Event")
            dtstart = current_evt.get("DTSTART", "")
            desc = current_evt.get("DESCRIPTION", "")
            
            # Extract YYYY-MM-DD from DTSTART
            # Format could be DTSTART;VALUE=DATE:20260919 or DTSTART:20260919T140000Z
            date_match = re.search(r'(\d{4})(\d{2})(\d{2})', dtstart)
            time_match = re.search(r'T(\d{2})(\d{2})', dtstart)
            
            if date_match:
                y, m, d = date_match.groups()
                date_str = f"{y}-{m}-{d}"
                time_str = "All Day"
                if time_match:
                    hh, mm = int(time_match.group(1)), int(time_match.group(2))
                    period = "AM" if hh < 12 else "PM"
                    hh12 = hh % 12 or 12
                    time_str = f"{hh12:02d}:{mm:02d} {period}"
                
                events.append({
                    "date": date_str,
                    "time": time_str,
                    "title": summary,
                    "desc": desc,
                    "category": "external",
                    "tag": provider_name,
                    "badge_color": provider_color,
                    "source": "external_ical"
                })
        elif in_event:
            parts = line_s.split(':', 1)
            if len(parts) == 2:
                key_part = parts[0].split(';')[0].upper()
                current_evt[key_part] = parts[1]
                
    return events

def fetch_external_feed(feed_id, url, name="External", color="#3b82f6"):
    """Download and parse an external iCal/webcal feed with 15-minute caching"""
    now = time.time()
    if feed_id in _EXTERNAL_EVENTS_CACHE and (now - _EXTERNAL_EVENTS_CACHE[feed_id]["time"]) < 900:
        return _EXTERNAL_EVENTS_CACHE[feed_id]["events"]
        
    try:
        # Convert webcal:// to https://
        clean_url = url.strip()
        if clean_url.startswith("webcal://"):
            clean_url = "https://" + clean_url[9:]
            
        req = urllib.request.Request(clean_url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; HomelabDashboardCalendar/1.0)"
        })
        with urllib.request.urlopen(req, timeout=6) as response:
            content = response.read().decode('utf-8', errors='ignore')
            evts = parse_ics_feed(content, provider_name=name, provider_color=color)
            _EXTERNAL_EVENTS_CACHE[feed_id] = {"events": evts, "time": now}
            return evts
    except Exception as e:
        print(f"[CalendarSync] Error fetching feed '{name}' from {url}: {e}")
        return []

def get_synced_external_events_for_month(year, month):
    """Aggregate all active external feeds for the requested month"""
    data = load_calendar_data()
    feeds = data.get("feeds", [])
    month_prefix = f"{year:04d}-{month:02d}"
    
    aggregated = {}  # {date_str: [event, ...]}
    
    for f in feeds:
        if not f.get("enabled", True):
            continue
        evts = fetch_external_feed(
            f.get("id"),
            f.get("url"),
            f.get("name", "External"),
            f.get("color", "#3b82f6")
        )
        for e in evts:
            if e["date"].startswith(month_prefix):
                aggregated.setdefault(e["date"], []).append(e)
                
    return aggregated

def generate_homelab_ics_feed(server_url=None):
    """
    Generate standard RFC 5545 .ics calendar feed of all Homelab events
    so users can subscribe on their iPhone, Mac, Google Calendar, or Outlook.
    """
    if not server_url:
        try:
            from card_manager import get_host_lan_ip
            server_url = f"http://{get_host_lan_ip()}:8095"
        except Exception:
            server_url = "http://localhost:8095"
    data = load_calendar_data()
    days = data.get("days", {})
    
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Homelab Hub//Server Dashboard Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Homelab Server & Energy Ledger",
        "X-WR-TIMEZONE:America/Toronto",
        "X-WR-CALDESC:Real-time automated backups, Docker fleet updates, maintenance logs, and daily energy costs."
    ]
    
    now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    for date_str, dinfo in sorted(days.items()):
        clean_date = date_str.replace('-', '')
        
        # 1. Daily Energy Cost Event
        eng = dinfo.get("energy")
        if eng and eng.get("kwh", 0) > 0:
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:energy-{date_str}@homelab.local",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{clean_date}",
                f"SUMMARY:⚡ Energy: {eng['kwh']:.3f} kWh (${eng['cost']:.2f})",
                f"DESCRIPTION:Daily power consumption: {eng['kwh']:.3f} kWh\\nEstimated Cost: ${eng['cost']:.2f}\\nAverage Draw: {eng.get('avg_watts', 0)} Watts",
                f"URL:{server_url}",
                "STATUS:CONFIRMED",
                "TRANSP:TRANSPARENT",
                "END:VEVENT"
            ])
            
        # 2. Server & User Events
        for ev in dinfo.get("events", []):
            ev_id = ev.get("id", f"{date_str}-{int(time.time())}")
            title = ev.get("title", "Server Event").replace(';', '\\;').replace(',', '\\,')
            desc = ev.get("desc", "").replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')
            tag = ev.get("tag", "Homelab")
            
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{ev_id}@homelab.local",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{clean_date}",
                f"SUMMARY:[{tag}] {title}",
                f"DESCRIPTION:{desc}",
                f"URL:{server_url}",
                "STATUS:CONFIRMED",
                "TRANSP:TRANSPARENT",
                "END:VEVENT"
            ])
            
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
