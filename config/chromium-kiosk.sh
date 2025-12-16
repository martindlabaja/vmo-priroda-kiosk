#!/bin/bash
# Chromium Kiosk Mode Launcher for Raspberry Pi
# Nature of Olomouc Region Museum Kiosk
#
# This script launches Chromium in fullscreen kiosk mode
# pointing to the local Flask server.

# Configuration
KIOSK_URL="${KIOSK_URL:-http://localhost:5000}"
DISPLAY="${DISPLAY:-:0}"

# Wait for X server to be ready
while ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
    echo "Waiting for X server..."
    sleep 1
done

# Wait for Flask server to be ready
echo "Waiting for Flask server at $KIOSK_URL..."
for i in {1..30}; do
    if curl -s "$KIOSK_URL" > /dev/null; then
        echo "Flask server is ready"
        break
    fi
    sleep 1
done

# Disable screen blanking and DPMS
xset -display "$DISPLAY" s off
xset -display "$DISPLAY" s noblank
xset -display "$DISPLAY" -dpms

# Hide mouse cursor after 0.1 seconds of inactivity
unclutter -idle 0.1 -root &

# Clear any Chromium crash flags
CHROMIUM_DIR="$HOME/.config/chromium"
if [ -d "$CHROMIUM_DIR" ]; then
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' \
        "$CHROMIUM_DIR/Default/Preferences" 2>/dev/null
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' \
        "$CHROMIUM_DIR/Default/Preferences" 2>/dev/null
fi

# Launch Chromium in kiosk mode
exec chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-translate \
    --disable-features=TranslateUI \
    --disable-component-update \
    --disable-background-networking \
    --disable-sync \
    --disable-default-apps \
    --disable-extensions \
    --disable-plugins \
    --disable-dev-shm-usage \
    --disable-gpu-compositing \
    --no-first-run \
    --start-fullscreen \
    --start-maximized \
    --window-size=1920,1080 \
    --window-position=0,0 \
    --check-for-update-interval=31536000 \
    --touch-events=enabled \
    --overscroll-history-navigation=0 \
    --autoplay-policy=no-user-gesture-required \
    --user-data-dir="$HOME/.config/chromium-kiosk" \
    "$KIOSK_URL"
