#!/bin/bash
# Raspberry Pi Setup Script for Příroda Olomouckého Kraje Kiosk
#
# This script sets up a fresh Raspberry Pi for running the kiosk application.
# Run as root or with sudo.
#
# Usage: sudo ./setup-raspberry-pi.sh

set -e

# Configuration
INSTALL_DIR="/home/pi/priroda-kiosk"
LOG_DIR="/var/log/priroda-kiosk"
PI_USER="pi"

echo "========================================"
echo "Příroda Kiosk - Raspberry Pi Setup"
echo "========================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup-raspberry-pi.sh)"
    exit 1
fi

# Update system
echo ""
echo "[1/8] Updating system packages..."
apt-get update
apt-get upgrade -y

# Install required packages
echo ""
echo "[2/8] Installing required packages..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    chromium-browser \
    unclutter \
    xdotool \
    x11-xserver-utils \
    curl \
    git

# Create log directory
echo ""
echo "[3/8] Creating log directory..."
mkdir -p "$LOG_DIR"
chown "$PI_USER:$PI_USER" "$LOG_DIR"

# Create installation directory if it doesn't exist
echo ""
echo "[4/8] Setting up application directory..."
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Please copy the priroda-kiosk folder to $INSTALL_DIR first"
    echo "Then run this script again."
    exit 1
fi

chown -R "$PI_USER:$PI_USER" "$INSTALL_DIR"

# Set up Python virtual environment
echo ""
echo "[5/8] Setting up Python virtual environment..."
su - "$PI_USER" -c "cd $INSTALL_DIR && python3 -m venv venv"
su - "$PI_USER" -c "cd $INSTALL_DIR && ./venv/bin/pip install --upgrade pip"
su - "$PI_USER" -c "cd $INSTALL_DIR && ./venv/bin/pip install -r requirements.txt"

# Make scripts executable
echo ""
echo "[6/8] Setting up scripts..."
chmod +x "$INSTALL_DIR/config/chromium-kiosk.sh"

# Install systemd services
echo ""
echo "[7/8] Installing systemd services..."
cp "$INSTALL_DIR/config/priroda-kiosk.service" /etc/systemd/system/
cp "$INSTALL_DIR/config/priroda-chromium.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable priroda-kiosk.service
systemctl enable priroda-chromium.service

# Configure auto-login for kiosk user
echo ""
echo "[8/8] Configuring auto-login..."
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $PI_USER --noclear %I \$TERM
EOF

# Configure X to start on login
if ! grep -q "startx" /home/$PI_USER/.bashrc; then
    echo "" >> /home/$PI_USER/.bashrc
    echo "# Auto-start X for kiosk mode" >> /home/$PI_USER/.bashrc
    echo '[[ -z $DISPLAY && $XDG_VTNR -eq 1 ]] && startx' >> /home/$PI_USER/.bashrc
fi

# Create minimal X startup
cat > /home/$PI_USER/.xinitrc << 'EOF'
#!/bin/bash
# Disable screen saver and power management
xset s off
xset s noblank
xset -dpms

# Start window manager or just run chromium
exec /home/pi/priroda-kiosk/config/chromium-kiosk.sh
EOF
chown "$PI_USER:$PI_USER" /home/$PI_USER/.xinitrc
chmod +x /home/$PI_USER/.xinitrc

echo ""
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Copy your content data to $INSTALL_DIR/data/"
echo "2. Reboot the Raspberry Pi: sudo reboot"
echo ""
echo "The kiosk should start automatically after reboot."
echo ""
echo "Manual service control:"
echo "  sudo systemctl start priroda-kiosk    # Start Flask server"
echo "  sudo systemctl status priroda-kiosk   # Check server status"
echo "  sudo systemctl stop priroda-kiosk     # Stop server"
echo ""
echo "View logs:"
echo "  sudo journalctl -u priroda-kiosk -f   # Flask logs"
echo "  sudo journalctl -u priroda-chromium -f # Browser logs"
