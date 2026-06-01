#!/usr/bin/env python3
"""
Setup script — à exécuter UNE FOIS sur le VPS pour obtenir un token OAuth
autorisé pour l'API GitHub Copilot.

Usage : python3 setup_copilot_token.py

Le token sera sauvegardé dans config.ini sous [github] copilot_token
"""
import requests
import configparser
import time
import sys
import os

# Client ID de l'extension VS Code GitHub Copilot
COPILOT_CLIENT_ID = "Iv1.b507a08c87ecfe98"

def main():
    print("=== GitHub Copilot Token Setup ===\n")

    # Étape 1 : demande de device code
    resp = requests.post(
        "https://github.com/login/device/code",
        headers={"Accept": "application/json"},
        data={
            "client_id": COPILOT_CLIENT_ID,
            "scope": "read:user",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_uri = data["verification_uri"]
    interval = data.get("interval", 5)
    expires_in = data.get("expires_in", 900)

    print(f"1. Ouvre cette URL dans ton navigateur :")
    print(f"   {verification_uri}\n")
    print(f"2. Saisis ce code : {user_code}\n")
    print(f"3. Ce script se terminera automatiquement une fois autorisé...\n")

    # Étape 2 : polling jusqu'à autorisation
    deadline = time.time() + expires_in
    access_token = None
    while time.time() < deadline:
        time.sleep(interval)
        poll = requests.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": COPILOT_CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            },
            timeout=15,
        )
        poll.raise_for_status()
        result = poll.json()
        error = result.get("error")
        if error == "authorization_pending":
            print("En attente de l'autorisation...", end="\r")
            continue
        elif error == "slow_down":
            interval += 5
            continue
        elif error:
            print(f"\nErreur : {error} — {result.get('error_description', '')}")
            sys.exit(1)
        access_token = result.get("access_token")
        break

    if not access_token:
        print("\nExpiration du délai. Relancez le script.")
        sys.exit(1)

    print(f"\n✓ Token obtenu : {access_token[:12]}...")

    # Étape 3 : vérifier que le token fonctionne pour Copilot
    check = requests.get(
        "https://api.github.com/copilot_internal/v2/token",
        headers={
            "Authorization": f"token {access_token}",
            "editor-version": "vscode/1.96.0",
            "editor-plugin-version": "copilot-chat/0.26.0",
            "user-agent": "GitHubCopilotChat/0.26.0",
        },
        timeout=15,
    )
    if check.status_code != 200:
        print(f"\n✗ Le token ne fonctionne pas pour Copilot : {check.status_code} {check.text[:200]}")
        print("Assure-toi que ce compte GitHub a un abonnement Copilot actif.")
        sys.exit(1)
    print("✓ Token Copilot validé avec succès !")

    # Étape 4 : écrire dans config.ini
    cfg_path = os.path.join(os.path.dirname(__file__), "config.ini")
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path)
    if not cfg.has_section("github"):
        cfg.add_section("github")
    cfg.set("github", "copilot_token", access_token)
    with open(cfg_path, "w") as f:
        cfg.write(f)

    print(f"\n✓ Token sauvegardé dans config.ini [github] copilot_token")
    print("Redémarre le serveur Flask pour prendre en compte le changement.")

if __name__ == "__main__":
    main()
