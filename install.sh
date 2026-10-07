#!/bin/bash
set -e

APP_DIR="/home/pi/escape-room-control"
SERVICE_FILE="/etc/systemd/system/escape-room.service"

echo "=== Escape Room Control installatie ==="

if [ "$(whoami)" != "pi" ]; then
    echo "Dit installatiebestand verwacht gebruiker 'pi'."
    exit 1
fi

echo "[1/6] Systeempakketten installeren..."
sudo apt update
sudo apt install -y \
    git \
    python3-venv \
    python3-pip \
    python3-lgpio

echo "[2/6] Python virtual environment maken..."
cd "$APP_DIR"

rm -rf .venv
python3 -m venv --system-site-packages .venv

echo "[3/6] Python dependencies installeren..."
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r requirements.txt

echo "[4/6] Sudo-rechten voor poweroff/reboot instellen..."
echo 'pi ALL=(root) NOPASSWD: /usr/sbin/poweroff, /usr/sbin/reboot' | \
    sudo tee /etc/sudoers.d/escape-room >/dev/null
sudo chmod 440 /etc/sudoers.d/escape-room

echo "[5/6] Systemd service installeren..."
sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Escape Room Control
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/.venv/bin"
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable escape-room.service
sudo systemctl restart escape-room.service

echo "[6/6] Installatie controleren..."
sleep 3

if systemctl is-active --quiet escape-room.service; then
    echo
    echo "Escape Room Control draait."
    echo "Open: http://$(hostname -I | awk '{print $1}'):8000"
else
    echo
    echo "FOUT: escape-room.service draait niet."
    sudo systemctl status escape-room.service --no-pager
    exit 1
fi
