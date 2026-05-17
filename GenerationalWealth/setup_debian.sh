#!/bin/bash
# Setup script for GenerationalWealth on Debian 13 (Trixie)
set -e

echo "=== GenerationalWealth — Setup Debian 13 ==="

# ---- System dependencies for Chromium headless (Playwright & Selenium) ----
echo "[1/4] Installation des dépendances système Chromium..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    libnspr4 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libglib2.0-0 \
    libdbus-1-3 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxshmfence1 \
    fonts-liberation \
    ca-certificates

# libasound2 a été renommé en libasound2t64 sur Debian 13
apt-get install -y libasound2t64 2>/dev/null || apt-get install -y libasound2 2>/dev/null || true

# ---- Chromium système pour Selenium ----
echo "[2/4] Installation de Chromium système (pour Selenium)..."
apt-get install -y --no-install-recommends chromium chromium-driver 2>/dev/null || \
apt-get install -y --no-install-recommends chromium-browser 2>/dev/null || true

# ---- Python venv ----
echo "[3/4] Création du venv Python et installation des dépendances..."
apt-get install -y python3-venv python3-pip -qq

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ---- Playwright : installer les navigateurs + dépendances ----
echo "[4/4] Installation des navigateurs Playwright..."
python3 -m playwright install chromium
python3 -m playwright install-deps chromium 2>/dev/null || true

# ---- Tor (proxy SOCKS5 pour bypasser les blocages IP) ----
echo "[5/5] Installation de Tor..."
apt-get install -y tor
# Activer le control port sans mot de passe (loopback uniquement)
grep -q "ControlPort 9051" /etc/tor/torrc || echo -e "\nControlPort 9051\nCookieAuthentication 0" >> /etc/tor/torrc
systemctl enable tor
systemctl restart tor

echo ""
echo "=== Setup terminé ==="
echo "Lancez le backend avec :"
echo "  source venv/bin/activate && GROQ_API_KEY='votre_clé' python3 backend.py"
