# Situation Mirror

Situation Mirror turns a second 800 × 480 display and an original Raspberry Pi Zero W into a lightweight bedroom repeater for the main Situation Monitor. The SDR receiver, `readsb`, and internet feeds remain on the primary WOPR. The Zero receives a compact JSON snapshot over the trusted local network and renders its own large-type Pygame interface.

This avoids video streaming and keeps the original single-core Zero W useful. The tested installation used:

- Source: Raspberry Pi Zero 2 W running `SituationMonitor_v2.py` and `readsb`
- Client: Raspberry Pi Zero W Rev 1.1 with 512 MB RAM
- Displays: 800 × 480 HDMI
- Raspberry Pi OS desktop with automatic login

## Screens

The mirror rotates every 12 seconds through:

1. Bedroom status with time, current weather, contact count, and nearest aircraft
2. Live 50 NM (93 km) radar with military highlighting and nearest-track details
3. Five-day forecast with large high and low temperatures
4. Two large current headlines

The client uses F1–F4 during development and hides the pointer in fullscreen operation.

Open [`preview.html`](preview.html) on a regular computer for a simulated layout preview. The preview does not connect to live feeds.

## Files

- `mirror_server.py` — LAN-only relay for the primary WOPR
- `mirror_client.py` — fullscreen Pygame client for the Pi Zero W
- `situation-mirror.desktop` — client desktop-autostart entry
- `wopr-labwc-autostart` — example primary-WOPR Labwc startup file
- `preview.html` — self-contained simulated browser preview

## Configuration

Before installation, edit these values as needed:

In `mirror_server.py`:

```python
HOME_LAT, HOME_LON = 35.0000, -97.0000
RANGE_NM = 50.0
```

Use the receiver's approximate coordinates. Avoid publishing precise private coordinates unintentionally.

In `mirror_client.py`:

```python
SERVER = "http://192.168.1.52:8765/snapshot"
```

Replace the address with the primary WOPR's reserved LAN address. Assigning a DHCP reservation is recommended so the address does not change.

## Requirements

The primary WOPR needs Python 3 and readable `readsb` aircraft JSON at one of the paths listed near the top of `mirror_server.py`.

The client needs Python 3 and Pygame:

```bash
sudo apt update
sudo apt install python3-pygame
```

## Install the relay on the primary WOPR

Copy `mirror_server.py` to `/home/pi/mirror_server.py`, then test it:

```bash
python3 /home/pi/mirror_server.py
```

From another trusted LAN device, open `http://WOPR_ADDRESS:8765/snapshot`. It should return JSON containing `aircraft`, `weather`, and `news` sections.

For Raspberry Pi OS with Labwc, preserve the existing Situation Monitor line and add:

```text
/usr/bin/python3 /home/pi/mirror_server.py >>/home/pi/mirror_server.log 2>&1 &
```

The included `wopr-labwc-autostart` shows both launch lines. Back up the existing file before replacing or editing it.

## Install the client on the Pi Zero W

Copy `mirror_client.py` to `/home/pi/mirror_client.py` and test it from the graphical desktop:

```bash
python3 /home/pi/mirror_client.py
```

For automatic startup, copy `situation-mirror.desktop` to:

```text
/home/pi/.config/autostart/situation-mirror.desktop
```

Disable or move any previous display application's desktop entry so two fullscreen programs do not start together.

## Failure behavior

- Feed requests run on a background thread and cannot freeze the display loop.
- The client retains its most recent successful snapshot during a temporary network failure.
- Feed and connection failures are shown in the header.
- The relay caches weather for ten minutes and headlines for five minutes.
- No SDR hardware is required on the client.

The relay has no authentication and listens on the local network. Use it only on a trusted LAN; do not forward TCP port 8765 from the router.

## Rollback

Remove or disable `situation-mirror.desktop` and restore the previous display application's autostart entry. On the primary WOPR, remove only the `mirror_server.py` launch line and leave the existing `SituationMonitor_v2.py` line intact.
