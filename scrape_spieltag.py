#!/usr/bin/env python3
"""
Scraper für kicker.de Spieltagsdaten → CSV im Transferbrett-Format

Verwendung:
  python scrape_spieltag.py --spieltag 4 --saison 2025-26

Ausgabe:
  Spieltag4_Noten.csv  (Verein;Status;Spieler;Punkte;RoteKarte;GelbRoteKarte;Vorlagen;Tore;SpielerDesSpiels)

Benötigt:
  pip install playwright beautifulsoup4
  playwright install chromium
"""

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

# Setze DEBUG_PLAYER=Nachname (env var) um für einen einzelnen Spieler den
# rohen Scraper-Rohtext (Note, Tor-Zeilen) auf der Konsole mitzuloggen, z.B.:
#   set DEBUG_PLAYER=Petkov & python scrape_spieltag.py --spieltag 1
DEBUG_PLAYER = os.environ.get("DEBUG_PLAYER", "").strip()

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Fehlende Pakete. Bitte installieren:\n  pip install playwright beautifulsoup4\n  playwright install chromium")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright fehlt. Bitte installieren:\n  pip install playwright\n  playwright install chromium")

# Punktekoeffizient pro Position
GOAL_COEF = {"GOALKEEPER": 6, "DEFENDER": 5, "MIDFIELDER": 4, "FORWARD": 3}

POS_MAP = {
    "GOALKEEPER": "GOALKEEPER", "DEFENDER": "DEFENDER",
    "MIDFIELDER": "MIDFIELDER", "FORWARD": "FORWARD",
    "Tor": "GOALKEEPER", "Abwehr": "DEFENDER",
    "Mittelfeld": "MIDFIELDER", "Sturm": "FORWARD",
}

TEAM_NAMES = {
    "Bor. Mönchengladbach": "Borussia Mönchengladbach",
    "Bor. Dortmund": "Borussia Dortmund",
    "Bayern München": "FC Bayern München",
    "Werder Bremen": "SV Werder Bremen",
}


def load_player_positions(path):
    positions = {}
    if not path or not Path(path).exists():
        return positions
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = row.get("Angezeigter Name (kurz)", "").strip()
            pos = POS_MAP.get(row.get("Position", "").strip(), "FORWARD")
            if name:
                positions[name] = pos
    print(f"  → {len(positions)} Spieler mit Positionen geladen")
    return positions


def get_html(page, url, wait_selector=None):
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if wait_selector:
        try:
            page.wait_for_selector(wait_selector, timeout=10000)
        except Exception:
            pass
    time.sleep(1.5)
    # Cloudflare-Challenge erkennen und warten bis aufgelöst
    for _ in range(10):
        html = page.content()
        if "data-cfasync" in html or "cmsg" in html and "<a " not in html:
            print("  Cloudflare-Challenge erkannt, warte 3s ...")
            time.sleep(3)
            html = page.content()
        else:
            return html
    return page.content()


def parse_grade(text):
    text = text.strip().replace(",", ".")
    match = re.search(r"(\d+\.\d+)$", text)
    if match:
        val = float(match.group(1))
        if 1.0 <= val <= 6.0:
            return val
    return None


def calc_points(p):
    status = p["_status"]
    grade = p["_grade"]
    pos = p["_position"]
    tga = p.get("_tGA", 1)

    status_pts = 4 if status == "start" else (2 if status == "sub" else 0)
    grade_pts = round((3.5 - grade) * 4, 1) if grade is not None else 0
    coef = GOAL_COEF.get(pos, 3)
    goal_pts = p["Tore"] * coef
    assist_pts = p["Vorlagen"] * 2
    red_pts = p["RoteKarte"] * (-6)
    yr_pts = p["GelbRoteKarte"] * (-3)
    sds_pts = 3 if p["SpielerDesSpiels"] else 0
    cs_pts = 2 if (pos == "GOALKEEPER" and tga == 0 and status == "start") else 0

    return round(status_pts + grade_pts + goal_pts + assist_pts + red_pts + yr_pts + sds_pts + cs_pts)


def scrape_game(page, url, player_positions):
    print(f"  Scrape: {url}")
    html = get_html(page, url, wait_selector="div.kick__lineup-text")
    soup = BeautifulSoup(html, "html.parser")

    # Teams
    team_els = soup.select("div.kick__v100-gameCell__team__name")
    team_home = TEAM_NAMES.get(
        team_els[0].get_text(strip=True), team_els[0].get_text(strip=True)
    ) if team_els else "Unbekannt"
    team_away = TEAM_NAMES.get(
        team_els[1].get_text(strip=True), team_els[1].get_text(strip=True)
    ) if len(team_els) > 1 else "Unbekannt"

    # Ergebnis
    goals_home = goals_away = 0
    score_els = soup.select("div.kick__v100-scoreCell__scoreHolder span, div[class*='score']")
    nums = [el.get_text(strip=True) for el in score_els if re.match(r"^\d+$", el.get_text(strip=True))]
    if DEBUG_PLAYER:
        print(f"  DEBUG Ergebnis: {len(score_els)} score-Elemente, davon rein-numerisch: {nums}")
    if len(nums) >= 2:
        try:
            goals_home, goals_away = int(nums[0]), int(nums[1])
        except ValueError:
            pass
    if DEBUG_PLAYER:
        print(f"  DEBUG Ergebnis: goals_home={goals_home} goals_away={goals_away} (für Weiße-Weste-Berechnung)")

    # Spieler des Spiels
    sds_name = None
    try:
        spielinfo_url = url.replace("/schema", "/spielinfo")
        sds_html = get_html(page, spielinfo_url)
        sds_soup = BeautifulSoup(sds_html, "html.parser")
        for sel in ["[class*='gameinfo__person']", "[class*='spielerDesSpiels']", "[class*='player-of-match']"]:
            el = sds_soup.select_one(sel)
            if el:
                sds_name = el.get_text(strip=True)
                break
        if DEBUG_PLAYER:
            print(f"  DEBUG SdS: spielinfo_url={spielinfo_url} -> gefundener Name='{sds_name}'")
    except Exception as e:
        if DEBUG_PLAYER:
            print(f"  DEBUG SdS: Fehler beim Laden von spielinfo: {e}")

    # kicker.de liefert den Spieler-des-Spiels-Namen als "Nachname, Vorname"
    # (z.B. "Petkov, Lukas"), die Startelf-Liste aber als "Initiale Nachname"
    # (z.B. "L. Petkov") -- Abgleich über den Nachnamen-Teil vor dem Komma.
    sds_surname = sds_name.split(",")[0].strip() if sds_name else None

    def make_player(name, status, grade, team, tga):
        pos = player_positions.get(name, "FORWARD")
        is_sds = bool(sds_surname) and name.strip().endswith(sds_surname)
        return {
            "Verein": team, "Status": "Start" if status == "start" else "Bank",
            "Spieler": name, "RoteKarte": 0, "GelbRoteKarte": 0,
            "Vorlagen": 0, "Tore": 0, "SpielerDesSpiels": 1 if is_sds else 0,
            "_status": status, "_grade": grade, "_position": pos, "_tGA": tga,
        }

    # Startelf (erste 22 Lineup-Links: 11 Heim + 11 Auswärts)
    all_lineup = soup.select("div.kick__lineup-text__unorderedList a")
    home_lineup = all_lineup[:11]
    away_lineup = all_lineup[11:22]

    players = []
    for a in home_lineup:
        txt = a.get_text(strip=True)
        name = re.sub(r"[\d,\.]+$", "", txt).strip()
        grade = parse_grade(txt)
        if DEBUG_PLAYER and DEBUG_PLAYER in name:
            print(f"  DEBUG Note: '{name}' Rohtext='{txt}' -> geparste Note={grade}")
        players.append(make_player(name, "start", grade, team_home, goals_away))
    for a in away_lineup:
        txt = a.get_text(strip=True)
        name = re.sub(r"[\d,\.]+$", "", txt).strip()
        grade = parse_grade(txt)
        if DEBUG_PLAYER and DEBUG_PLAYER in name:
            print(f"  DEBUG Note: '{name}' Rohtext='{txt}' -> geparste Note={grade}")
        players.append(make_player(name, "start", grade, team_away, goals_home))

    player_lookup = {p["Spieler"]: p for p in players}

    # Einwechslungen
    # WICHTIG: nicht über [class*='substitutions__team'] gehen -- dieser Selektor matcht
    # 10 Container pro Spiel (nicht 2), und Container[1] (das vermeintliche Auswärtsteam)
    # ist dabei durchgehend leer. Die echten Auswärts-Einwechslungsdaten stecken in
    # data-grid__main[1] (dieselben Container, die auch die Karten-Sektion nutzt).
    sub_grid_sections = soup.select("[class*='data-grid__main']")
    if DEBUG_PLAYER:
        print(f"  DEBUG Einwechslungen: {len(sub_grid_sections)} data-grid__main-Container gefunden")
    for si, (team, tga) in enumerate([(team_home, goals_away), (team_away, goals_home)]):
        if si >= len(sub_grid_sections):
            break
        player_els = sub_grid_sections[si].select("[class*='substitutions__player']")
        if DEBUG_PLAYER:
            print(f"  DEBUG Einwechslungen ({team}): {len(player_els)} Elemente: {[e.get_text(strip=True) for e in player_els]}")
        for el in player_els:
            txt = el.get_text(strip=True)
            name = re.sub(r"[\d,\.]+$", "", txt).strip()
            if not name:
                continue
            if name in player_lookup:
                # Bereits als Startelf-Spieler erfasst -- das ist der Ausgewechselte,
                # nicht überschreiben (sonst geht seine echte Startelf-Note verloren).
                if DEBUG_PLAYER and DEBUG_PLAYER in name:
                    print(f"  DEBUG Einwechslung: '{name}' bereits in Startelf, übersprungen (ausgewechselter Spieler)")
                continue
            grade = parse_grade(txt)
            if DEBUG_PLAYER and DEBUG_PLAYER in name:
                print(f"  DEBUG Note (Einwechslung): '{name}' Rohtext='{txt}' -> geparste Note={grade}")
            p = make_player(name, "sub", grade, team, tga)
            players.append(p)
            player_lookup[name] = p

    # Bank (kein Einsatz)
    bench_sections = soup.select("[class*='reservebank'] div.kick__lineup-text a, "
                                  "[class*='bench'] div.kick__lineup-text a")
    if DEBUG_PLAYER:
        bench_container_count = len(soup.select("[class*='reservebank'], [class*='bench']"))
        print(f"  DEBUG Bank: {bench_container_count} Bank-Container, {len(bench_sections)} Bank-Spieler-Elemente gefunden: {[a.get_text(strip=True) for a in bench_sections]}")
    seen_bench = set()
    for a in bench_sections:
        name = a.get_text(strip=True)
        if name and name not in player_lookup and name not in seen_bench:
            # Zuordnung Heim/Auswärts unklar → versuche über Eltern-Element
            team = team_home  # Fallback
            p = make_player(name, "bench", None, team, 0)
            players.append(p)
            seen_bench.add(name)

    # Tore
    goal_rows = soup.select("[class*='goals__row']")
    if DEBUG_PLAYER:
        print(f"  DEBUG Tore: {len(goal_rows)} goals__row-Elemente im HTML gefunden (jedes echte Tor sollte nur 1x auftauchen)")
    for row in goal_rows:
        scorer_el = row.select_one("[class*='substitutions--hide-mobile']")
        subtxt = (row.select_one("[class*='goals__player-subtxt']") or row).get_text()
        assist_els = row.select("[class*='assist__player']")
        assist_name_raw = assist_els[-1].get_text(strip=True) if assist_els else None
        # kicker.de stellt dem Namen die Schussart voran ("Linksschuss, Onyeka",
        # "Rechtsschuss, L. Petkov") -- nur den Teil nach dem letzten Komma behalten.
        assist_name = assist_name_raw.split(",")[-1].strip() if assist_name_raw else None

        if DEBUG_PLAYER and ((scorer_el and DEBUG_PLAYER in scorer_el.get_text(strip=True)) or (assist_name and DEBUG_PLAYER in assist_name)):
            scorer_dbg = scorer_el.get_text(strip=True) if scorer_el else None
            print(f"  DEBUG Tor-Zeile: Torschütze='{scorer_dbg}' subtxt='{subtxt.strip()[:60]}' Vorlage(roh)='{assist_name_raw}' Vorlage(bereinigt)='{assist_name}' assist_els_count={len(assist_els)} row-class='{row.get('class')}'")
        if scorer_el:
            scorer = scorer_el.get_text(strip=True)
            if scorer in player_lookup and "Eigentor" not in subtxt:
                player_lookup[scorer]["Tore"] += 1
        if assist_name and assist_name in player_lookup:
            player_lookup[assist_name]["Vorlagen"] += 1

    # Karten
    for sec in soup.select("[class*='data-grid__main']"):
        p_els = sec.select("[class*='substitutions__player']")
        icon_els = sec.select("[class*='icon-box']")
        if DEBUG_PLAYER and p_els:
            print(f"  DEBUG Karten: {len(p_els)} substitutions__player-Elemente: {[e.get_text(strip=True) for e in p_els]}, {len(icon_els)} icon-Elemente")
        for i, p_el in enumerate(p_els[::2]):
            name = p_el.get_text(strip=True)
            if i < len(icon_els):
                box = str(icon_els[i])
                if DEBUG_PLAYER and DEBUG_PLAYER in name:
                    print(f"  DEBUG Karte: '{name}' icon-box='{box[:100]}'")
                if "ticker-icon-array" in box or "GelbRot" in box:
                    if name in player_lookup:
                        player_lookup[name]["GelbRoteKarte"] = 1
                elif "icon-Rot" in box:
                    if name in player_lookup:
                        player_lookup[name]["RoteKarte"] = 1

    # Punkte berechnen
    for p in players:
        p["Punkte"] = calc_points(p)

    return players


def get_game_links(page, saison, spieltag):
    url = f"https://www.kicker.de/bundesliga/spieltag/{saison}/{spieltag}"
    print(f"Lade Spieltag-Übersicht: {url}")
    html = get_html(page, url, wait_selector="a[href*='bundesliga']")
    soup = BeautifulSoup(html, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Format 1: /bundesliga/spieltag/.../schema oder /analyse
        # Format 2 (ab 2026-27): /team-gegen-team-YYYY-bundesliga-ID/analyse
        # Format 3 (ab 2026-27): /team-gegen-team-YYYY-bundesliga-ID (ohne Suffix)
        if "/schema" in href or "/analyse" in href:
            href = href.replace("/analyse", "/schema")
            full = "https://www.kicker.de" + href if href.startswith("/") else href
            if full not in links:
                links.append(full)
        elif re.search(r"-bundesliga-\d+/?$", href):
            href = href.rstrip("/")
            full = "https://www.kicker.de" + href if href.startswith("/") else href
            full = full + "/schema"
            if full not in links:
                links.append(full)

    # Debug: zeige Seiteninhalt wenn keine Links gefunden
    if not links:
        all_hrefs = [a["href"] for a in soup.find_all("a", href=True)]
        print(f"  DEBUG: {len(all_hrefs)} hrefs total, aktuelle URL: {page.url}")
        print(f"  DEBUG HTML-Anfang (500 Zeichen): {html[:500].replace(chr(10),' ')}")

    print(f"  → {len(links)} Spiele gefunden")
    return links


def write_csv(players, output_path):
    cols = ["Verein", "Status", "Spieler", "Punkte",
            "RoteKarte", "GelbRoteKarte", "Vorlagen", "Tore", "SpielerDesSpiels"]

    team_rows = {}
    for p in players:
        team = p["Verein"]
        team_rows.setdefault(team, []).append(p)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(";".join(cols) + "\n")
        for team, rows in team_rows.items():
            team_total = 0
            for p in rows:
                f.write(";".join([
                    p["Verein"], p["Status"], p["Spieler"], str(p["Punkte"]),
                    str(p["RoteKarte"]), str(p["GelbRoteKarte"]),
                    str(p["Vorlagen"]), str(p["Tore"]), str(p["SpielerDesSpiels"]),
                ]) + "\n")
                if p["_status"] in ("start", "sub"):
                    team_total += p["Punkte"]
            f.write(f"{team};Teampunkte;;{team_total};;;;;\n")

    teams = len(team_rows)
    print(f"\n✓ Gespeichert: {output_path}  ({len(players)} Spieler, {teams} Teams)")


def main():
    parser = argparse.ArgumentParser(description="kicker.de Spieltag-Scraper")
    parser.add_argument("--spieltag", type=int, required=True)
    parser.add_argument("--saison", default="2025-26")
    parser.add_argument("--interactive", default="players-se-k00012026.csv",
                        help="Pfad zur Interactive-Spielerliste (für Positionen)")
    parser.add_argument("--output", default=None)
    parser.add_argument("--headless", action="store_true", default=False,
                        help="Browser unsichtbar ausführen (Standard: sichtbar)")
    args = parser.parse_args()

    output = args.output or f"Spieltag{args.spieltag}_Noten.csv"

    positions = {}
    if args.interactive:
        print(f"Lade Spielerpositionen aus: {args.interactive}")
        positions = load_player_positions(args.interactive)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        context = browser.new_context(
            locale="de-DE",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # kicker.de Startseite zuerst laden und Cloudflare passieren lassen
        print("Verbinde mit kicker.de ...")
        page.goto("https://www.kicker.de", wait_until="domcontentloaded", timeout=30000)
        for _ in range(8):
            time.sleep(3)
            if "data-cfasync" not in page.content():
                break
            print("  Cloudflare auf Startseite, warte ...")

        game_links = get_game_links(page, args.saison, args.spieltag)
        if not game_links:
            browser.close()
            sys.exit("Keine Spiel-Links gefunden.")

        all_players = []
        for link in game_links:
            try:
                game_players = scrape_game(page, link, positions)
                all_players.extend(game_players)
                time.sleep(1.5)
            except Exception as e:
                print(f"  WARNUNG: Spiel übersprungen ({e})")

        browser.close()

    if not all_players:
        sys.exit("Keine Spielerdaten gefunden.")

    write_csv(all_players, output)
    print(f"\nNächster Schritt: '{output}' im Tool über 'Spieltag importieren' hochladen")


if __name__ == "__main__":
    main()
