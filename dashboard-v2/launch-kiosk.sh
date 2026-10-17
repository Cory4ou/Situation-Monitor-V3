#!/bin/sh
set -eu
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
until curl -fsS http://127.0.0.1:8080/api/config >/dev/null; do sleep 2; done
if command -v wtype >/dev/null 2>&1; then
    (sleep 20; wtype -M alt -M logo -P h -p h -m logo -m alt) &
fi
exec /usr/bin/chromium --ozone-platform=wayland --password-store=basic --no-memcheck --disable-gpu --disable-extensions --disable-background-networking --kiosk --no-first-run --disable-session-crashed-bubble --user-data-dir="$HOME/.config/wopr-chromium" http://127.0.0.1:8080
