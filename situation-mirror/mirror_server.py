#!/usr/bin/env python3
"""Small LAN-only data relay for the Situation Mirror client."""

import json
import math
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST, PORT = "0.0.0.0", 8765
HOME_LAT, HOME_LON = 35.0000, -97.0000
RANGE_NM = 50.0
AIRCRAFT_PATHS = (
    Path("/run/readsb/aircraft.json"),
    Path("/var/run/readsb/aircraft.json"),
    Path("/run/dump1090-fa/aircraft.json"),
)
RSS_FEEDS = (
    ("NATIONAL", "https://www.cbsnews.com/latest/rss/us"),
    ("TECH", "https://www.cbsnews.com/latest/rss/technology"),
    ("SPACE", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
)

cache = {}
locks = {}


def fetch(url, timeout=7):
    request = urllib.request.Request(url, headers={"User-Agent": "Situation-Mirror/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read(2_000_001)
    if len(payload) > 2_000_000:
        raise ValueError("feed too large")
    return payload


def cached(name, seconds, loader):
    lock = locks.setdefault(name, threading.Lock())
    with lock:
        old = cache.get(name)
        if old and time.time() - old["attempt"] < seconds:
            return old["value"]
        try:
            value = {"ok": True, "updated": time.time(), "data": loader()}
        except Exception as error:
            value = {
                "ok": False,
                "updated": old["value"].get("updated") if old else None,
                "data": old["value"].get("data") if old else None,
                "error": type(error).__name__,
            }
        cache[name] = {"attempt": time.time(), "value": value}
        return value


def distance_bearing(lat, lon):
    p1, p2 = math.radians(HOME_LAT), math.radians(lat)
    dp = math.radians(lat - HOME_LAT)
    dl = math.radians(lon - HOME_LON)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    distance = 3440.065 * 2 * math.asin(min(1, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return distance, math.degrees(math.atan2(y, x)) % 360


def aircraft_data():
    path = next((item for item in AIRCRAFT_PATHS if item.exists()), None)
    if not path:
        raise FileNotFoundError("readsb aircraft.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    planes = []
    for item in raw.get("aircraft", []):
        if item.get("seen", 999) > 45 or item.get("seen_pos", 999) > 45:
            continue
        if "lat" not in item or "lon" not in item:
            continue
        distance, bearing = distance_bearing(float(item["lat"]), float(item["lon"]))
        if distance > RANGE_NM:
            continue
        icao = str(item.get("hex", "")).lstrip("~").upper()
        flight = str(item.get("flight") or "").strip().upper()
        military = icao.startswith("AE") or flight.startswith(("RCH", "REACH", "EVAC", "SAM", "SPAR"))
        planes.append({
            "id": icao,
            "flight": flight or icao or "UNKNOWN",
            "distance": round(distance, 1),
            "bearing": round(bearing, 1),
            "altitude": item.get("alt_baro"),
            "speed": item.get("gs"),
            "track": item.get("track"),
            "military": military,
        })
    planes.sort(key=lambda item: item["distance"])
    return {"planes": planes, "messages": raw.get("messages", 0), "range_nm": RANGE_NM}


def weather_data():
    query = urllib.parse.urlencode({
        "latitude": HOME_LAT,
        "longitude": HOME_LON,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "America/Chicago",
        "forecast_days": 5,
    })
    raw = json.loads(fetch("https://api.open-meteo.com/v1/forecast?" + query))
    daily = raw["daily"]
    days = []
    for index, date in enumerate(daily["time"]):
        days.append({
            "date": date,
            "high": round(daily["temperature_2m_max"][index]),
            "low": round(daily["temperature_2m_min"][index]),
            "rain": daily["precipitation_probability_max"][index],
            "code": daily["weather_code"][index],
        })
    return {"current": raw["current"], "days": days}


def news_data():
    stories = []
    for category, url in RSS_FEEDS:
        try:
            root = ET.fromstring(fetch(url))
            for item in root.findall(".//item")[:2]:
                title = " ".join((item.findtext("title") or "").split())
                if title:
                    stories.append({"category": category, "title": title})
        except Exception:
            continue
    if not stories:
        raise ValueError("no headlines")
    return stories[:4]


def snapshot():
    return {
        "server_time": time.time(),
        "aircraft": cached("aircraft", 2, aircraft_data),
        "weather": cached("weather", 600, weather_data),
        "news": cached("news", 300, news_data),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urllib.parse.urlparse(self.path).path not in ("/", "/snapshot"):
            self.send_error(404)
            return
        payload = json.dumps(snapshot(), separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    print(f"Situation Mirror relay listening on {HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
