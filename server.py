#!/usr/bin/env python3
"""
Lokaler Scraper-Server für das Transferbrett-Tool.
Startet einen HTTP-Server auf Port 7431, der kicker.de-Daten abruft und als CSV zurückgibt.

Verwendung:
  pip install flask playwright beautifulsoup4
  playwright install chromium
  python server.py

Der Browser ruft dann: http://localhost:7431/scrape?spieltag=3&saison=2025-26
"""

import csv
import io
import os
import sys
import threading

try:
    from flask import Flask, request, Response
    from flask_cors import CORS
except ImportError:
    sys.exit(
        "Fehlende Pakete. Bitte installieren:\n"
        "  pip install flask flask-cors playwright beautifulsoup4\n"
        "  playwright install chromium"
    )

# scrape_spieltag.py muss im selben Ordner liegen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from scrape_spieltag import (
        get_game_links, scrape_game, load_player_positions,
        calc_points, TEAM_NAMES
    )
    from playwright.sync_api import sync_playwright
except ImportError as e:
    sys.exit(f"Import-Fehler: {e}\nBitte 'pip install playwright beautifulsoup4' ausführen.")

app = Flask(__name__)
CORS(app)  # erlaubt Anfragen vom Browser (andere Origin)

INTERACTIVE_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "players-se-k00012026.csv")

_scrape_lock = threading.Lock()


def build_csv(players):
    cols = ["Verein", "Status", "Spieler", "Punkte",
            "RoteKarte", "GelbRoteKarte", "Vorlagen", "Tore", "SpielerDesSpiels"]

    out = io.StringIO()
    out.write(";".join(cols) + "\n")

    team_rows = {}
    for p in players:
        team_rows.setdefault(p["Verein"], []).append(p)

    for team, rows in team_rows.items():
        team_total = 0
        for p in rows:
            out.write(";".join([
                p["Verein"], p["Status"], p["Spieler"], str(p["Punkte"]),
                str(p["RoteKarte"]), str(p["GelbRoteKarte"]),
                str(p["Vorlagen"]), str(p["Tore"]), str(p["SpielerDesSpiels"]),
            ]) + "\n")
            if p["_status"] in ("start", "sub"):
                team_total += p["Punkte"]
        out.write(f"{team};Teampunkte;;{team_total};;;;;\n")

    return out.getvalue()


@app.route("/scrape")
def scrape():
    spieltag = request.args.get("spieltag", type=int)
    saison = request.args.get("saison", "2025-26")

    if not spieltag or spieltag < 1 or spieltag > 34:
        return Response("Ungültiger Spieltag (1–34 erwartet).", status=400)

    if not _scrape_lock.acquire(blocking=False):
        return Response("Scraper läuft bereits. Bitte warten.", status=429)

    try:
        print(f"\n>>> Scrape Spieltag {spieltag}, Saison {saison} ...")
        positions = load_player_positions(INTERACTIVE_CSV)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False)
            context = browser.new_context(
                locale="de-DE",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            import time
            page.goto("https://www.kicker.de", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            game_links = get_game_links(page, saison, spieltag)
            if not game_links:
                browser.close()
                return Response("Keine Spiele gefunden.", status=404)

            all_players = []
            for link in game_links:
                try:
                    all_players.extend(scrape_game(page, link, positions))
                    time.sleep(1.5)
                except Exception as e:
                    print(f"  WARNUNG: {link} übersprungen ({e})")

            browser.close()

        if not all_players:
            return Response("Keine Spielerdaten gefunden.", status=404)

        csv_text = build_csv(all_players)
        print(f">>> Fertig: {len(all_players)} Spieler")

        return Response(
            csv_text,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=Spieltag{spieltag}_Noten.csv"},
        )

    except Exception as e:
        print(f">>> FEHLER: {e}")
        return Response(f"Fehler beim Scrapen: {e}", status=500)
    finally:
        _scrape_lock.release()


@app.route("/status")
def status():
    busy = not _scrape_lock.acquire(blocking=False)
    if not busy:
        _scrape_lock.release()
    return {"running": busy}


@app.route("/")
def index():
    return (
        "<h2>Transferbrett Scraper-Server</h2>"
        "<p>Läuft. Endpunkte:</p>"
        "<ul>"
        "<li><a href='/scrape?spieltag=1&saison=2025-26'>/scrape?spieltag=1&amp;saison=2025-26</a></li>"
        "<li><a href='/status'>/status</a></li>"
        "</ul>"
    )


if __name__ == "__main__":
    print("=" * 50)
    print("Transferbrett Scraper-Server")
    print(f"Spielerliste: {INTERACTIVE_CSV}")
    print("URL: http://localhost:7431")
    print("=" * 50)
    app.run(host="127.0.0.1", port=7431, debug=False)
