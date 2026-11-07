#!/usr/bin/env python3
"""800x480 Pygame client for the Situation Mirror relay."""

import json
import math
import threading
import time
import urllib.request
from datetime import datetime

import pygame

WIDTH, HEIGHT = 800, 480
SERVER = "http://192.168.1.52:8765/snapshot"
PAGE_SECONDS = 12
FPS = 24

BLACK = (0, 1, 8)
WHITE = (234, 255, 255)
CYAN = (0, 234, 255)
PINK = (255, 47, 175)
VIOLET = (143, 80, 255)
GREEN = (66, 255, 176)
DIM = (23, 32, 61)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.NOFRAME)
pygame.display.set_caption("SITUATION MIRROR")
pygame.mouse.set_visible(False)
clock = pygame.time.Clock()


def font(size, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    try:
        return pygame.font.Font(path, size)
    except OSError:
        return pygame.font.SysFont("monospace", size, bold=bold)


F14, F17, F20, F24, F30, F38, F50, F76 = [font(n, n >= 30) for n in (14, 17, 20, 24, 30, 38, 50, 76)]


class Feed:
    def __init__(self):
        self.data = None
        self.updated = 0
        self.fetching = False
        self.error = "WAITING FOR WOPR"

    def update(self):
        if self.fetching or time.time() - self.updated < 3:
            return
        self.fetching = True
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            request = urllib.request.Request(SERVER, headers={"User-Agent": "Situation-Mirror/1.0"})
            with urllib.request.urlopen(request, timeout=3) as response:
                incoming = json.load(response)
            self.data = incoming
            self.updated = time.time()
            self.error = ""
        except Exception as error:
            self.updated = time.time()
            self.error = type(error).__name__.upper()
        finally:
            self.fetching = False


feed = Feed()


def put(value, x, y, use=F20, color=WHITE, align="left"):
    image = use.render(str(value), True, color)
    if align == "center":
        x -= image.get_width() // 2
    elif align == "right":
        x -= image.get_width()
    screen.blit(image, (int(x), int(y)))


def line(x1, y1, x2, y2, color=VIOLET, width=1):
    pygame.draw.line(screen, color, (x1, y1), (x2, y2), width)


def box(rect, color=VIOLET):
    pygame.draw.rect(screen, color, rect, 1)


def header(title, subtitle, page):
    put("▌", 14, 7, F30, PINK)
    put(title, 31, 8, F30, WHITE)
    put(subtitle, 31, 42, F17, CYAN)
    put("● LINKED" if not feed.error else "○ " + feed.error, 782, 12, F14, GREEN if not feed.error else PINK, "right")
    line(18, 68, 782, 68, CYAN, 2)
    put(f"PAGE {page} / 4", 782, 451, F14, VIOLET, "right")
    line(18, 444, 782, 444, CYAN, 2)


def weather_label(code):
    if code is None: return "UNAVAILABLE"
    if code == 0: return "CLEAR"
    if code in (1, 2): return "PARTLY CLOUDY"
    if code == 3: return "CLOUDY"
    if code in (45, 48): return "FOG"
    if code in (51, 53, 55, 56, 57): return "DRIZZLE"
    if code in (61, 63, 65, 66, 67, 80, 81, 82): return "RAIN"
    if code in (71, 73, 75, 77, 85, 86): return "SNOW"
    if code in (95, 96, 99): return "STORMS"
    return "MIXED"


def good(section):
    return feed.data and feed.data.get(section, {}).get("data")


def draw_status():
    header("SITUATION MIRROR", "BEDROOM STATUS / LIVE FROM WOPR", 1)
    now = datetime.now()
    aircraft = good("aircraft") or {"planes": []}
    weather = good("weather") or {"current": {}}
    planes = aircraft.get("planes", [])
    current = weather.get("current", {})
    box((18, 82, 465, 350)); box((495, 82, 287, 168)); box((495, 264, 287, 168))
    put("LOCAL TIME", 31, 94, F20, VIOLET)
    put(now.strftime("%I:%M"), 28, 127, F76, WHITE)
    put(now.strftime("%A  %B %d").upper(), 31, 215, F24, CYAN)
    put("NEAREST AIRCRAFT", 31, 300, F20, VIOLET)
    if planes:
        nearest = planes[0]
        put(nearest["flight"], 31, 332, F38, PINK if nearest.get("military") else WHITE)
        put(f'{nearest["distance"]:.1f} NM / {nearest["distance"] * 1.852:.1f} KM', 31, 383, F20, GREEN)
    else:
        put("NO POSITIONED TRACKS", 31, 340, F24, WHITE)
    put("OUTSIDE / OKLAHOMA", 510, 94, F17, VIOLET)
    temperature = current.get("temperature_2m")
    put("--°" if temperature is None else f"{round(temperature)}°", 510, 125, F50, WHITE)
    put(weather_label(current.get("weather_code")), 510, 194, F20, CYAN)
    put("AIRSPACE / 50 NM", 510, 277, F17, VIOLET)
    put(f"{len(planes)} CONTACTS", 510, 310, F38, CYAN)
    level = "LOW" if len(planes) < 5 else "MODERATE" if len(planes) < 12 else "HIGH"
    put(level, 510, 370, F24, GREEN)


def draw_radar():
    header("LIVE AIRSPACE", "50 NM / 93 KM ADS-B MIRROR", 2)
    aircraft = good("aircraft") or {"planes": []}
    planes = aircraft.get("planes", [])
    cx, cy, radius = 225, 258, 155
    for ring in range(1, 5):
        pygame.draw.circle(screen, VIOLET, (cx, cy), radius * ring // 4, 1)
    line(cx - radius, cy, cx + radius, cy); line(cx, cy - radius, cx, cy + radius)
    sweep = time.monotonic() * 1.3
    line(cx, cy, cx + math.sin(sweep) * radius, cy - math.cos(sweep) * radius, CYAN)
    for plane in planes:
        angle = math.radians(plane["bearing"])
        distance = min(radius, plane["distance"] / 50 * radius)
        x = cx + math.sin(angle) * distance
        y = cy - math.cos(angle) * distance
        color = PINK if plane.get("military") else WHITE
        pygame.draw.circle(screen, color, (int(x), int(y)), 5 if plane.get("military") else 4)
        put(plane["flight"][:9], x + 7, y - 8, F14, color)
    line(465, 82, 465, 430)
    put("NEAREST TRACKS", 490, 91, F24, CYAN)
    for index, plane in enumerate(planes[:5]):
        y = 134 + index * 57
        put(plane["flight"][:12], 490, y, F20, PINK if plane.get("military") else WHITE)
        put(f'{plane["distance"]:.1f} NM', 770, y, F17, GREEN, "right")
        altitude = plane.get("altitude")
        speed = plane.get("speed")
        detail = (f"{altitude:,} FT" if isinstance(altitude, (int, float)) else "ALT --") + "  " + (f"{round(speed)} KT" if isinstance(speed, (int, float)) else "SPD --")
        put(detail, 490, y + 25, F14, VIOLET)
    if not planes:
        put("NO POSITIONED TRACKS", 625, 230, F20, WHITE, "center")


def draw_forecast():
    header("FIVE DAY OUTLOOK", "OKLAHOMA / BEDROOM READABILITY MODE", 3)
    weather = good("weather") or {"days": []}
    days = weather.get("days", [])
    if not days:
        put("FORECAST UNAVAILABLE", 400, 225, F30, PINK, "center")
        return
    for index, day in enumerate(days[:5]):
        x = 18 + index * 153
        box((x, 84, 145, 345))
        date = datetime.strptime(day["date"], "%Y-%m-%d")
        put(date.strftime("%a").upper(), x + 11, 96, F24, PINK if index == 0 else WHITE)
        put(date.strftime("%b %d").upper(), x + 11, 128, F14, VIOLET)
        put(f'{day["high"]}°', x + 9, 174, F38, WHITE)
        put(f'LOW {day["low"]}°', x + 11, 232, F20, CYAN)
        put(weather_label(day.get("code"))[:12], x + 11, 286, F14, GREEN)
        put(f'RAIN {day.get("rain", 0)}%', x + 11, 360, F17, PINK if day.get("rain", 0) >= 50 else VIOLET)


def wrapped(value, width):
    words, lines, current = value.split(), [], ""
    for word in words:
        candidate = word if not current else current + " " + word
        if len(candidate) > width:
            lines.append(current); current = word
        else:
            current = candidate
    if current: lines.append(current)
    return lines


def draw_news():
    header("INTELLIGENCE", "LARGE-TYPE BEDROOM EDITION", 4)
    stories = good("news") or []
    if not stories:
        put("HEADLINES UNAVAILABLE", 400, 225, F30, PINK, "center")
        return
    y = 87
    for index, story in enumerate(stories[:2]):
        put(f'{index + 1:02d} / {story["category"]}', 25, y, F17, PINK)
        y += 31
        for row in wrapped(story["title"].upper(), 42)[:2]:
            put(row, 25, y, F30, WHITE); y += 39
        y += 12
        line(25, y, 775, y, DIM); y += 11


drawers = (draw_status, draw_radar, draw_forecast, draw_news)
page, next_page, running = 0, time.monotonic() + PAGE_SECONDS, True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif pygame.K_F1 <= event.key <= pygame.K_F4:
                page = event.key - pygame.K_F1
                next_page = time.monotonic() + PAGE_SECONDS
    if time.monotonic() >= next_page:
        page = (page + 1) % len(drawers)
        next_page = time.monotonic() + PAGE_SECONDS
    feed.update()
    screen.fill(BLACK)
    drawers[page]()
    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
