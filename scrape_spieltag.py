#!/usr/bin/env python3
"""
Scraper für kicker.de Spieltagsdaten → CSV im Transferbrett-Format

Verwendung:
  python3 scrape_spieltag.py --spieltag 3 --saison 2025-26

Ausgabe:
  SpieltagN_Noten.csv  (Verein;Status;Spieler;Punkte;RoteKarte;GelbRoteKarte;Vorlagen;Tore;SpielerDesSpiels)

Benötigt:
  pip install requests beautifulsoup4
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Fehlende Pakete. Bitte installieren:\n  pip install requests beautifulsoup4")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Punktekoeffizient pro Position
GOAL_COEF = {"GOALKEEPER": 6, "DEFENDER": 5, "MIDFIELDER": 4, "FORWARD": 3}

# Positionsname-Mapping (kicker Interactive → intern)
POS_MAP = {
    "GOALKEEPER": "GOALKEEPER",
    "DEFENDER": "DEFENDER",
    "MIDFIELDER": "MIDFIELDER",
    "FORWARD": "FORWARD",
    "Tor": "GOALKEEPER",
    "Abwehr": "DEFENDER",
    "Mittelfeld": "MIDFIELDER",
    "Sturm": "FORWARD",
}

# Vereinsname-Normalisierung (kicker.de → gewünschter Anzeigename)
TEAM_NAMES = {
    "Bor. Mönchengladbach": "Borussia Mönchengladbach",
    "Bor. Dortmund": "Borussia Dortmund",
    "1. FC Union Berlin": "1. FC Union Berlin",
    "Bayer 04 Leverkusen": "Bayer 04 Leverkusen",
    "Bayern München": "FC Bayern München",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "SC Freiburg": "SC Freiburg",
    "RB Leipzig": "RB Leipzig",
    "VfB Stuttgart": "VfB Stuttgart",
    "Werder Bremen": "SV Werder Bremen",
    "1. FSV Mainz 05": "1. FSV Mainz 05",
    "TSG Hoffenheim": "TSG Hoffenheim",
    "FC Augsburg": "FC Augsburg",
    "1. FC Köln": "1. FC Köln",
    "FC Schalke 04": "FC Schalke 04",
    "Hamburger SV": "Hamburger SV",
    "SV 07 Elversberg": "SV 07 Elversberg",
    "SC Paderborn 07": "SC Paderborn 07",
}


def get_soup(url, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except requests.RequestException as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                raise RuntimeError(f"Fehler beim Laden von {url}: {e}")


def load_player_positions(interactive_csv_path):
    """Lädt Spielerpositionen aus der Interactive-CSV (für Punkteberechnung)."""
    positions = {}
    if not Path(interactive_csv_path).exists():
        print(f"WARNUNG: {interactive_csv_path} nicht gefunden – verwende FORWARD als Standard")
        return positions
    with open(interactive_csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = row.get("Angezeigter Name (kurz)", "").strip()
            pos = POS_MAP.get(row.get("Position", "").strip(), "FORWARD")
            if name:
                positions[name] = pos
    return positions


def get_game_links(saison, spieltag):
    """Holt alle Spiel-Links für einen Spieltag."""
    url = f"https://www.kicker.de/bundesliga/spieltag/{saison}/{spieltag}"
    print(f"Lade Spieltag-Übersicht: {url}")
    soup = get_soup(url)

    links = []
    for a in soup.select("a[href*='/schema']"):
        href = a.get("href", "")
        if "/schema" in href:
            full = "https://www.kicker.de" + href if href.startswith("/") else href
            if full not in links:
                links.append(full)

    # Fallback: alle Spiellink-Indikatoren
    if not links:
        for el in soup.select("[class*='gameRow']"):
            for a in el.find_all("a", href=True):
                href = a["href"]
                if "/schema" in href or "/analyse" in href:
                    href = href.replace("/analyse", "/schema")
                    full = "https://www.kicker.de" + href if href.startswith("/") else href
                    if full not in links:
                        links.append(full)

    print(f"  → {len(links)} Spiele gefunden")
    return links


def parse_grade(text):
    """Extrahiert kicker-Note aus einem String (z.B. 'Kobel3,5' → 3.5)."""
    text = text.strip().replace(",", ".")
    match = re.search(r"(\d+\.\d+|\d+)$", text)
    if match:
        val = float(match.group(1))
        if 1.0 <= val <= 6.0:
            return val
    return None


def calc_points(player):
    """Berechnet Managerspiel-Punkte nach kicker-Formel."""
    status = player["_status"]  # start/sub/bench
    grade = player["_grade"]
    pos = player["_position"]
    goals = player["Tore"]
    assists = player["Vorlagen"]
    red = player["RoteKarte"]
    yr = player["GelbRoteKarte"]
    sds = player["SpielerDesSpiels"]
    is_gk = pos == "GOALKEEPER"
    tga = player.get("_tGA", 1)  # Gegentore des Teams

    status_pts = 4 if status == "start" else (2 if status == "sub" else 0)
    grade_pts = round((3.5 - grade) * 4, 1) if grade is not None else 0
    coef = GOAL_COEF.get(pos, 3)
    goal_pts = goals * coef
    assist_pts = assists * 2
    red_pts = red * (-6)
    yr_pts = yr * (-3)
    sds_pts = 3 if sds else 0
    cs_pts = 2 if (is_gk and tga == 0 and status == "start") else 0

    total = status_pts + grade_pts + goal_pts + assist_pts + red_pts + yr_pts + sds_pts + cs_pts
    return round(total)


def scrape_game(url, player_positions):
    """Scrapt ein einzelnes Spiel und gibt Spieler-Daten zurück."""
    print(f"  Scrape: {url}")
    soup = get_soup(url)
    time.sleep(0.5)

    # Teamnamen
    team_els = soup.select("div.kick__v100-gameCell__team__name")
    team_home = team_els[0].get_text(strip=True) if len(team_els) > 0 else "Unbekannt"
    team_away = team_els[1].get_text(strip=True) if len(team_els) > 1 else "Unbekannt"

    # Ergebnis (für Clean Sheet)
    score_els = soup.select("div.kick__v100-scoreCell__scoreHolder div")
    try:
        goals_home = int(score_els[0].get_text(strip=True))
        goals_away = int(score_els[-1].get_text(strip=True))
    except (ValueError, IndexError):
        goals_home = goals_away = 0

    # Spieler des Spiels
    sds_name = None
    spielinfo_url = url.replace("/schema", "/spielinfo")
    try:
        sds_soup = get_soup(spielinfo_url)
        sds_el = sds_soup.select_one("[class*='gameinfo__person'], [class*='spielerDesSpiels']")
        if sds_el:
            sds_name = sds_el.get_text(strip=True)
    except Exception:
        pass

    players = []

    def add_players_from_section(section_soup, team, tga):
        # Startelf
        lineup_links = section_soup.select("div.kick__lineup-text__unorderedList a") if section_soup else []
        if not lineup_links:
            lineup_links = soup.select("div.kick__lineup-text a")

        # Trenne Startelf Heim/Auswärts (erste 11 / zweite 11)
        all_lineup = soup.select("div.kick__lineup-text__unorderedList a")
        return all_lineup

    # Alle Lineup-Einträge
    all_lineup = soup.select("div.kick__lineup-text__unorderedList a")
    home_lineup_raw = all_lineup[:11] if len(all_lineup) >= 11 else all_lineup
    away_lineup_raw = all_lineup[11:22] if len(all_lineup) >= 22 else []

    def process_lineup(lineup_raw, team, tga):
        result = []
        for a in lineup_raw:
            txt = a.get_text(strip=True)
            name_raw = re.sub(r"[\d,\.]+$", "", txt).strip()
            grade = parse_grade(txt)
            pos = player_positions.get(name_raw, "FORWARD")
            is_sds = sds_name and (name_raw in sds_name or sds_name in name_raw)
            p = {
                "Verein": TEAM_NAMES.get(team, team),
                "Status": "Start",
                "Spieler": name_raw,
                "RoteKarte": 0, "GelbRoteKarte": 0,
                "Vorlagen": 0, "Tore": 0,
                "SpielerDesSpiels": 1 if is_sds else 0,
                "_status": "start", "_grade": grade,
                "_position": pos, "_tGA": tga,
            }
            result.append(p)
        return result

    home_players = process_lineup(home_lineup_raw, team_home, goals_away)
    away_players = process_lineup(away_lineup_raw, team_away, goals_home)

    # Einwechslungen
    sub_sections = soup.select("[class*='substitutions__team']")
    for si, (team, tga) in enumerate([(team_home, goals_away), (team_away, goals_home)]):
        if si >= len(sub_sections):
            break
        sec = sub_sections[si]
        for pair in zip(
            sec.select("[class*='substitutions__player']")[::2],
            sec.select("[class*='substitutions__player']")[1::2],
        ):
            in_txt = pair[0].get_text(strip=True)
            name_in = re.sub(r"[\d,\.]+$", "", in_txt).strip()
            grade = parse_grade(in_txt)
            pos = player_positions.get(name_in, "FORWARD")
            is_sds = sds_name and (name_in in sds_name or sds_name in name_in)
            p = {
                "Verein": TEAM_NAMES.get(team, team),
                "Status": "Bank",
                "Spieler": name_in,
                "RoteKarte": 0, "GelbRoteKarte": 0,
                "Vorlagen": 0, "Tore": 0,
                "SpielerDesSpiels": 1 if is_sds else 0,
                "_status": "sub", "_grade": grade,
                "_position": pos, "_tGA": tga,
            }
            if si == 0:
                home_players.append(p)
            else:
                away_players.append(p)

    # Bankplätze
    bench_sections = soup.select("[class*='bank'], [class*='bench'], [class*='reservebank']")
    for si, (team, tga) in enumerate([(team_home, goals_away), (team_away, goals_home)]):
        if si >= len(bench_sections):
            break
        sec = bench_sections[si]
        for a in sec.select("div.kick__lineup-text a"):
            name = a.get_text(strip=True)
            pos = player_positions.get(name, "FORWARD")
            p = {
                "Verein": TEAM_NAMES.get(team, team),
                "Status": "Bank",
                "Spieler": name,
                "RoteKarte": 0, "GelbRoteKarte": 0,
                "Vorlagen": 0, "Tore": 0,
                "SpielerDesSpiels": 0,
                "_status": "bench", "_grade": None,
                "_position": pos, "_tGA": tga,
            }
            if si == 0:
                home_players.append(p)
            else:
                away_players.append(p)

    all_players = home_players + away_players
    player_lookup = {p["Spieler"]: p for p in all_players}

    # Tore
    for goal_row in soup.select("[class*='goals__row']"):
        scorer = goal_row.select_one("[class*='substitutions--hide-mobile']")
        if not scorer:
            continue
        scorer_name = scorer.get_text(strip=True)
        subtxt_el = goal_row.select_one("[class*='goals__player-subtxt']")
        subtxt = subtxt_el.get_text(strip=True) if subtxt_el else ""
        assist_el = goal_row.select("[class*='assist__player']")
        assist_name = assist_el[-1].get_text(strip=True) if assist_el else None

        if scorer_name in player_lookup:
            if "Eigentor" not in subtxt:
                player_lookup[scorer_name]["Tore"] += 1
        if assist_name and assist_name in player_lookup:
            player_lookup[assist_name]["Vorlagen"] += 1

    # Karten
    card_sections = soup.select("[class*='karten'] [class*='data-grid__main'], "
                                "[class*='cards'] [class*='data-grid__main']")
    for sec in card_sections:
        for i, player_el in enumerate(sec.select("[class*='substitutions__player']")[::2]):
            name = player_el.get_text(strip=True)
            icon_box = sec.select("[class*='icon-box']")
            card_type = ""
            if i < len(icon_box):
                box_html = str(icon_box[i])
                if "ticker-icon-array" in box_html or "GelbRot" in box_html:
                    card_type = "yr"
                elif "icon-Rot" in box_html:
                    card_type = "red"
            if name in player_lookup:
                if card_type == "red":
                    player_lookup[name]["RoteKarte"] = 1
                elif card_type == "yr":
                    player_lookup[name]["GelbRoteKarte"] = 1

    # Punkte berechnen
    for p in all_players:
        p["Punkte"] = calc_points(p)

    return all_players


def write_csv(players, spieltag, output_path):
    cols = ["Verein", "Status", "Spieler", "Punkte",
            "RoteKarte", "GelbRoteKarte", "Vorlagen", "Tore", "SpielerDesSpiels"]

    team_rows = {}
    for p in players:
        team = p["Verein"]
        if team not in team_rows:
            team_rows[team] = []
        team_rows[team].append(p)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(";".join(cols) + "\n")
        for team, rows in team_rows.items():
            team_total = 0
            for p in rows:
                line = [
                    p["Verein"], p["Status"], p["Spieler"],
                    str(p["Punkte"]),
                    str(p["RoteKarte"]), str(p["GelbRoteKarte"]),
                    str(p["Vorlagen"]), str(p["Tore"]),
                    str(p["SpielerDesSpiels"]),
                ]
                f.write(";".join(line) + "\n")
                if p["_status"] != "bench":
                    team_total += p["Punkte"]
            f.write(f"{team};Teampunkte;;{team_total};;;;;\n")

    print(f"\n✓ Gespeichert: {output_path}  ({len(players)} Spieler, {len(team_rows)} Teams)")


def main():
    parser = argparse.ArgumentParser(description="kicker.de Spieltag-Scraper")
    parser.add_argument("--spieltag", type=int, required=True, help="Spieltagnummer (z.B. 3)")
    parser.add_argument("--saison", default="2025-26", help="Saison (z.B. 2025-26)")
    parser.add_argument(
        "--interactive",
        default="data/2526/interactive_2526_2025_07_30.csv",
        help="Pfad zur Interactive-Spielerliste (für Positionen)",
    )
    parser.add_argument("--output", default=None, help="Ausgabe-Dateiname (Standard: SpieltagN_Noten.csv)")
    args = parser.parse_args()

    output = args.output or f"Spieltag{args.spieltag}_Noten.csv"
    interactive_path = args.interactive

    # Spielerpositionen laden
    print(f"Lade Spielerpositionen aus: {interactive_path}")
    positions = load_player_positions(interactive_path)
    print(f"  → {len(positions)} Spieler geladen")

    # Spieltag scrapen
    try:
        game_links = get_game_links(args.saison, args.spieltag)
    except RuntimeError as e:
        sys.exit(f"Fehler: {e}")

    if not game_links:
        sys.exit("Keine Spiel-Links gefunden. Bitte Saison/Spieltag prüfen.")

    all_players = []
    for link in game_links:
        try:
            game_players = scrape_game(link, positions)
            all_players.extend(game_players)
            time.sleep(1)
        except Exception as e:
            print(f"  WARNUNG: Spiel übersprungen ({e})")

    if not all_players:
        sys.exit("Keine Spielerdaten gefunden.")

    write_csv(all_players, args.spieltag, output)
    print(f"\nNächster Schritt: '{output}' im Transferbrett-Tool über 'Spieltag importieren' hochladen")


if __name__ == "__main__":
    main()
