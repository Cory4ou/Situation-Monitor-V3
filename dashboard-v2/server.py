#!/usr/bin/env python3
"""WOPR local dashboard; Python 3.9+, standard library only."""
import json
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import threading
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json' if (ROOT / 'config.json').exists() else ROOT / 'config.example.json').read_text())
CACHE = {}
LOCKS = {}

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'WOPR-Situation-Monitor/1.0'})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = r.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('Feed too large')
        return data

def cached(key, ttl, load):
    with LOCKS.setdefault(key, threading.Lock()):
        old = CACHE.get(key)
        if old and time.time() - old['attempt'] < ttl:
            return old['result']
        try:
            result = {'ok': True, 'updated': time.time(), 'data': load()}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc), 'updated': old['result']['updated'] if old else None,
                      'data': old['result']['data'] if old else None}
        CACHE[key] = {'attempt': time.time(), 'result': result}
        return result

def origin():
    lat, lon = CONFIG.get('latitude'), CONFIG.get('longitude')
    if lat is None or lon is None:
        raise ValueError('Set latitude and longitude in config.json')
    return float(lat), float(lon)

def polar(lat, lon):
    a, b = map(math.radians, origin())
    c, d = math.radians(lat), math.radians(lon)
    h = math.sin((c-a)/2)**2 + math.cos(a)*math.cos(c)*math.sin((d-b)/2)**2
    distance = 3440.065 * 2 * math.asin(min(1, math.sqrt(h)))
    bearing = math.atan2(math.sin(d-b)*math.cos(c), math.cos(a)*math.sin(c)-math.sin(a)*math.cos(c)*math.cos(d-b))
    return distance, math.degrees(bearing) % 360

def aircraft():
    raw = json.loads(fetch(CONFIG['readsb_url']) if CONFIG.get('readsb_url') else Path(CONFIG['readsb_path']).read_bytes())
    now = time.time()
    if abs(now-float(raw['now'])) > 30:
        raise ValueError('readsb feed is stale')
    planes = []
    origin()
    for p in raw.get('aircraft', []):
        if p.get('seen', 999) > 30 or p.get('seen_pos', 999) > 30 or 'lat' not in p or 'lon' not in p:
            continue
        distance, bearing = polar(p['lat'], p['lon'])
        if distance > CONFIG['range_nm']:
            continue
        planes.append({'id': p.get('hex', ''), 'flight': p.get('flight', '').strip() or p.get('hex', '?'),
                       'alt': p.get('alt_baro'), 'speed': p.get('gs'), 'track': p.get('track', 0),
                       'distance': distance, 'bearing': bearing})
    return {'planes': sorted(planes, key=lambda p: p['distance']), 'messages': raw.get('messages')}

def weather():
    lat, lon = origin()
    query = urllib.parse.urlencode({'latitude': lat, 'longitude': lon,
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m', 'timezone': 'auto'})
    return json.loads(fetch('https://api.open-meteo.com/v1/forecast?' + query))['current']

def parse_feed(data, source):
    root = ET.fromstring(data)
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    items = []
    for node in root.findall('.//item') + root.findall('a:entry', ns):
        title = node.findtext('title') or node.findtext('a:title', namespaces=ns)
        link = node.findtext('link')
        if not link:
            el = node.find('a:link', ns)
            link = el.get('href', '') if el is not None else ''
        if title and urllib.parse.urlparse(link or '').scheme in ('https', 'http'):
            items.append({'title': title, 'url': link, 'source': source})
    return items[:20]

def news():
    rows, failed = [], []
    for feed in CONFIG.get('rss', []):
        try:
            rows.extend(parse_feed(fetch(feed['url']), feed['name']))
        except Exception:
            failed.append(feed['name'])
    if not rows:
        raise ValueError('No RSS headlines available')
    return {'items': rows, 'failed': failed}

def markets():
    if not CONFIG.get('markets_path'):
        return []
    path = Path(CONFIG['markets_path'])
    if time.time()-path.stat().st_mtime > 900:
        raise ValueError('Markets file is stale')
    return json.loads(path.read_text())



def alerts():
    lat, lon = origin()
    data = json.loads(fetch('https://api.weather.gov/alerts/active?point=' + str(lat) + ',' + str(lon)))
    return parse_alerts(data, time.time())

def parse_alerts(data, now):
    items = []
    for feature in data.get('features', []):
        p = feature.get('properties', {})
        if p.get('status') != 'Actual' or p.get('messageType') == 'Cancel':
            continue
        try:
            expiry = datetime.fromisoformat(str(p.get('expires') or '').replace('Z', '+00:00')).timestamp()
        except (ValueError, TypeError, KeyError):
            continue
        if expiry <= now:
            continue
        items.append({'event': p.get('event', 'Weather alert'), 'headline': p.get('headline', ''),
                      'severity': p.get('severity', 'Unknown'), 'expires': expiry,
                      'description': p.get('description', ''), 'instruction': p.get('instruction') or ''})
    items.sort(key=lambda a: {'Extreme':0, 'Severe':1, 'Moderate':2, 'Minor':3}.get(a['severity'],4))
    return {'items': items, 'source': 'NWS'}

def football():
    now = datetime.now(ZoneInfo('America/Chicago'))
    if now.weekday() not in (5, 6):
        return {'weekend': False, 'games': []}
    saturday = now.date() - timedelta(days=now.weekday()-5)
    dates = saturday.strftime('%Y%m%d')
    url = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=100&dates=' + dates
    data = json.loads(fetch(url))
    games = []
    for event in data.get('events', []):
        comp = event['competitions'][0]
        teams = sorted(comp['competitors'], key=lambda t: t.get('homeAway') == 'home')
        def rank(t):
            return t.get('curatedRank', {}).get('current', 99)
        if not any(1 <= rank(t) <= 25 for t in teams):
            continue
        status = comp.get('status', event.get('status', {}))
        state = status.get('type', {}).get('state', 'pre')
        if state == 'pre':
            detail = datetime.fromisoformat(event['date'].replace('Z', '+00:00')).astimezone(ZoneInfo('America/Chicago')).strftime('%a %I:%M %p CT')
        else:
            detail = status.get('type', {}).get('shortDetail', '')
        labels = []
        for t in teams:
            label = ('#'+str(rank(t))+' ' if rank(t)<=25 else '') + t['team']['abbreviation']
            if state != 'pre':
                label += ' ' + str(t.get('score', '0'))
            labels.append(label)
        games.append({'ou': any(t['team'].get('abbreviation') == 'OU' for t in teams), 'text': ' vs '.join(labels) + ' · ' + detail, 'state': state})
    games.sort(key=lambda g: {'in':0, 'pre':1, 'post':2}.get(g['state'],3))
    return {'weekend': True, 'games': games, 'source': 'ESPN'}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT/'static'), **kwargs)

    def do_GET(self):
        routes = {'/api/aircraft': ('aircraft', 2, aircraft), '/api/weather': ('weather', 600, weather),
                  '/api/news': ('news', 300, news), '/api/alerts': ('alerts', 60, alerts), '/api/football': ('football', 60, football), '/api/markets': ('markets', 60, markets)}
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/config':
            result = {k: CONFIG[k] for k in ('location', 'range_nm')}
        elif path in routes:
            result = cached(*routes[path])
        elif path == '/api/status':
            try:
                temp = float(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000
            except OSError:
                temp = None
            result = {'ok': True, 'temperature': temp}
        else:
            return super().do_GET()
        payload = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

if __name__ == '__main__':
    print('WOPR: http://%s:%s' % (CONFIG['host'], CONFIG['port']), flush=True)
    ThreadingHTTPServer((CONFIG['host'], CONFIG['port']), Handler).serve_forever()
