# Escape Pi installatie

## 1. Raspberry Pi OS installeren

Installeer Raspberry Pi OS Lite op een SD-kaart.

Gebruik bij voorkeur Raspberry Pi Imager en stel vooraf in:

- hostname: `escapepi`
- gebruiker: `pi`
- SSH: ingeschakeld
- netwerk: indien nodig Wi-Fi instellen

Start de Raspberry Pi en log in via SSH.

## 2. Systeem bijwerken en Git installeren

```bash
sudo apt update
sudo apt install -y git
```

## 3. Escape Room Control downloaden

```bash
cd ~
git clone https://github.com/jtuinman/escape-room-control.git
cd escape-room-control
```

## 4. Installatie uitvoeren

```bash
chmod +x install.sh
./install.sh
```

Het installatiescript installeert:

- Python virtual environment
- Python dependencies
- GPIO-ondersteuning via `lgpio`
- systemd-service voor automatisch starten

## 5. Controle

Controleer de service:

```bash
systemctl status escape-room.service --no-pager
```

De status moet zijn:

```text
active (running)
```

Test lokaal:

```bash
curl -I http://127.0.0.1:8000
```

Verwacht:

```text
HTTP/1.1 200 OK
```

De webinterface is bereikbaar via:

```text
http://<IP-ADRES-VAN-DE-PI>:8000
```

Het actuele IP-adres vind je met:

```bash
hostname -I
```

## 6. Herstarttest

```bash
sudo reboot
```

Na opnieuw inloggen:

```bash
systemctl status escape-room.service --no-pager
```

De Escape Room Control-service moet automatisch actief zijn.

## GitHub-toegang vanaf de Pi

Alleen nodig wanneer vanaf de Escape Pi zelf wijzigingen naar GitHub moeten worden gepusht.

Maak een SSH-key:

```bash
ssh-keygen -t ed25519 -C "escape-pi"
```

Toon de publieke key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Voeg deze op GitHub toe onder:

`Settings → SSH and GPG keys`

Test:

```bash
ssh -T git@github.com
```

Zet daarna de repository-remote op SSH:

```bash
git remote set-url origin git@github.com:jtuinman/escape-room-control.git
```

## Handige commando's

Service herstarten:

```bash
sudo systemctl restart escape-room.service
```

Service stoppen:

```bash
sudo systemctl stop escape-room.service
```

Service starten:

```bash
sudo systemctl start escape-room.service
```

Logs bekijken:

```bash
journalctl -u escape-room.service -f
```

Status bekijken:

```bash
systemctl status escape-room.service --no-pager
```
