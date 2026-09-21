#!/usr/bin/env python3
"""
Kicker Manager – Spieltag-Scraper
Lädt die Spieltag-Noten automatisch von kicker.de und schreibt sie direkt in Firebase.

Verwendung:
  python fetch_matchday.py --spieltag 3 --board <BOARD_ID>

BOARD_ID steht in der URL deines Transferbretts: ?board=xxxxx
SEASON_ID steht in der URL des Managerspiels: se-k00012026

Zugangsdaten via Umgebungsvariablen setzen (empfohlen):
  export KICKER_USER="deine@email.de"
  export KICKER_PASS="deinPasswort"

Oder direkt unten in KICKER_USER / KICKER_PASS eintragen (nicht committen!).
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata

import requests

# ===== Konfiguration =====
KICKER_USER  = os.environ.get("KICKER_USER", "")
KICKER_PASS  = os.environ.get("KICKER_PASS", "")
SEASON_ID    = "se-k00012026"          # aus der Manager-URL
FIREBASE_DB  = "https://transferbrett---kicker-manager-default-rtdb.europe-west1.firebasedatabase.app"
PLAYERS_FILE = os.path.join(os.path.dirname(__file__), "players_slim.json")

LOGIN_URL    = "https://secure.kicker.de/community/login"
# CSV-Export-URL – Spieltag {st} ersetzen
CSV_URL_TMPL = "https://www.kicker.de/managerspiel/service/spieltagExport/{season}/spieltag/{st}"


# ===== Hilfsfunktionen =====

def normalize(s: str) -> str:
    """Kleinbuchstaben, diakritische Zeichen entfernen."""
    s = s.lower().strip()
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def kicker_login(session: requests.Session) -> bool:
    """Loggt in kicker.de ein. Gibt True zurück wenn erfolgreich."""
    try:
        # Loginseite holen (CSRF-Token)
        r = session.get(LOGIN_URL, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"[Fehler] Login-Seite nicht erreichbar: {e}")
        return False

    # CSRF-Token aus dem Formular lesen
    csrf = ""
    m = re.search(r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']', r.text)
    if not m:
        m = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']_token["\']', r.text)
    if m:
        csrf = m.group(1)

    payload = {
        "nickname":  KICKER_USER,
        "password":  KICKER_PASS,
        "_token":    csrf,
        "redirect":  "",
    }
    try:
        r2 = session.post(LOGIN_URL, data=payload, timeout=15, allow_redirects=True)
        # Erfolg: kein Login-Formular mehr sichtbar
        if "logout" in r2.text.lower() or "abmelden" in r2.text.lower():
            print("[OK] Login erfolgreich.")
            return True
        # Alternativ: Cookie "kicker_session" gesetzt
        if "kicker_session" in session.cookies or "user_id" in session.cookies:
            print("[OK] Login erfolgreich (Cookie).")
            return True
        print("[Warnung] Login möglicherweise fehlgeschlagen (kein Logout-Link gefunden).")
        print("         Versuche trotzdem fortzufahren …")
        return True  # manchmal kein logout-Link sichtbar, aber trotzdem eingeloggt
    except Exception as e:
        print(f"[Fehler] Login-POST fehlgeschlagen: {e}")
        return False


def download_csv(session: requests.Session, spieltag: int) -> str | None:
    """Lädt die Spieltag-CSV von kicker.de herunter."""
    url = CSV_URL_TMPL.format(season=SEASON_ID, st=spieltag)
    print(f"[CSV] Lade: {url}")
    try:
        r = session.get(url, timeout=20)
        if r.status_code == 404:
            print(f"[Fehler] 404 – Spieltag {spieltag} noch nicht verfügbar oder URL falsch.")
            print("         Versuche alternative URL …")
            # Alternative URL-Muster ausprobieren
            alternatives = [
                f"https://www.kicker.de/managerspiel/service/noten/{SEASON_ID}/spieltag/{spieltag}/export",
                f"https://www.kicker.de/managerspiel/service/spieltagsnoten/{SEASON_ID}/spieltag/{spieltag}.csv",
                f"https://www.kicker.de/managerspiel/service/export/{SEASON_ID}/spieltag/{spieltag}",
            ]
            for alt in alternatives:
                print(f"         Probiere: {alt}")
                r = session.get(alt, timeout=20)
                if r.status_code == 200 and ";" in r.text:
                    print(f"[OK] CSV von Alternativ-URL geladen.")
                    return r.text
            return None
        r.raise_for_status()
        if ";" not in r.text:
            print("[Fehler] Antwort sieht nicht wie eine CSV aus (kein ';' gefunden).")
            print("         Mögliche Ursache: Login fehlgeschlagen oder falsche URL.")
            return None
        print(f"[OK] CSV geladen ({len(r.text)} Zeichen).")
        return r.text
    except Exception as e:
        print(f"[Fehler] CSV-Download: {e}")
        return None


def parse_csv(text: str) -> list[dict]:
    """Parst die Kicker-Manager-CSV in eine Liste von Zeilen-Dicts."""
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    header = lines[0].split(";")
    idx = {h.strip(): i for i, h in enumerate(header)}

    required = {"Verein", "Status", "Spieler", "Punkte"}
    missing = required - set(idx)
    if missing:
        print(f"[Fehler] CSV-Header unvollständig, fehlt: {missing}")
        print(f"         Gefundene Spalten: {list(idx)}")
        return []

    rows = []
    for line in lines[1:]:
        cols = line.split(";")
        status_raw = cols[idx["Status"]].strip() if idx["Status"] < len(cols) else ""
        if status_raw == "Teampunkte":
            continue
        rows.append({
            "club":          cols[idx["Verein"]].strip() if idx["Verein"] < len(cols) else "",
            "status":        "start" if status_raw == "Start" else "bench",
            "name":          cols[idx["Spieler"]].strip() if idx["Spieler"] < len(cols) else "",
            "points":        float(cols[idx["Punkte"]]) if idx["Punkte"] < len(cols) and cols[idx["Punkte"]].strip().lstrip("-").isdigit() else 0,
            "redCard":       cols[idx.get("RoteKarte", -1)].strip() == "1" if idx.get("RoteKarte", -1) != -1 and idx.get("RoteKarte", -1) < len(cols) else False,
            "yellowRedCard": cols[idx.get("GelbRoteKarte", -1)].strip() == "1" if idx.get("GelbRoteKarte", -1) != -1 and idx.get("GelbRoteKarte", -1) < len(cols) else False,
            "assists":       int(cols[idx["Vorlagen"]]) if "Vorlagen" in idx and idx["Vorlagen"] < len(cols) and cols[idx["Vorlagen"]].strip().lstrip("-").isdigit() else 0,
            "goals":         int(cols[idx["Tore"]]) if "Tore" in idx and idx["Tore"] < len(cols) and cols[idx["Tore"]].strip().lstrip("-").isdigit() else 0,
            "motm":          cols[idx.get("SpielerDesSpiels", -1)].strip() == "1" if idx.get("SpielerDesSpiels", -1) != -1 and idx.get("SpielerDesSpiels", -1) < len(cols) else False,
        })
    return rows


def load_players(path: str) -> list[dict]:
    """Lädt players_slim.json."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm_club(name: str) -> str:
    """Vereinsnamen normalisieren für Vergleich."""
    # häufige Abweichungen zwischen CSV und players_slim.json
    replacements = {
        "bor. mönchengladbach": "borussia mönchengladbach",
        "bor. dortmund":        "borussia dortmund",
        "werder bremen":        "sv werder bremen",
        "sv elversberg":        "sv 07 elversberg",
        "1. fc k":              "1. fc köln",
    }
    n = normalize(name)
    for k, v in replacements.items():
        if n.startswith(k):
            return v
    return n


def find_player(players: list[dict], club: str, short_name: str) -> dict | None:
    """
    Gleicht Verein + Kurzname aus der CSV gegen players_slim.json ab.
    Gleiche Logik wie findPlayerForMatchdayRow() in der JS-App.
    """
    nc = norm_club(club)
    nk = normalize(short_name)

    in_club = [p for p in players if norm_club(p["c"]) == nc]
    pool = in_club if in_club else players

    # 1. Exakter Kurzname-Treffer im Verein
    exact = [p for p in pool if normalize(p["k"]) == nk]
    if len(exact) == 1:
        return exact[0]

    # 2. Exakter Kurzname-Treffer ligaweit
    exact_any = [p for p in players if normalize(p["k"]) == nk]
    if len(exact_any) == 1:
        return exact_any[0]

    # 3. Kurzname enthält Short-Name oder umgekehrt
    contain = [p for p in pool if nk in normalize(p["k"]) or normalize(p["k"]) in nk]
    if len(contain) == 1:
        return contain[0]

    # 4. Vollname enthält Short-Name
    contain2 = [p for p in pool if nk in normalize(p["n"]) or any(part in normalize(p["n"]) for part in nk.split())]
    if len(contain2) == 1:
        return contain2[0]

    # 5. Nachname-Abgleich (letzter Teil des Vollnamens)
    def last(p):
        return normalize(p["n"]).split()[-1]
    surname = [p for p in pool if last(p) == nk or nk in last(p)]
    if len(surname) == 1:
        return surname[0]

    return None


def build_matchday_entry(rows: list[dict], players: list[dict]) -> tuple[dict, list]:
    """
    Konvertiert CSV-Zeilen in das Firebase-Matchday-Format.
    Gibt (players_dict, unmatched_rows) zurück.
    """
    matched = {}
    unmatched = []
    for row in rows:
        p = find_player(players, row["club"], row["name"])
        if p:
            matched[p["id"]] = {
                "points":        int(row["points"]),
                "status":        row["status"],
                "goals":         row["goals"],
                "assists":       row["assists"],
                "redCard":       row["redCard"],
                "yellowRedCard": row["yellowRedCard"],
                "motm":          row["motm"],
            }
        else:
            unmatched.append(row)
    return matched, unmatched


def push_to_firebase(board_id: str, spieltag: int, entry: dict) -> bool:
    """Schreibt den Spieltag-Eintrag via REST API in Firebase."""
    url = f"{FIREBASE_DB}/boards/{board_id}/matchdays/{spieltag}.json"
    print(f"[Firebase] Schreibe nach: boards/{board_id}/matchdays/{spieltag}")
    try:
        r = requests.put(url, json=entry, timeout=20)
        if r.status_code == 200:
            print(f"[OK] Firebase-Push erfolgreich.")
            return True
        else:
            print(f"[Fehler] Firebase antwortet mit Status {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"[Fehler] Firebase-Push: {e}")
        return False


# ===== Hauptprogramm =====

def main():
    parser = argparse.ArgumentParser(description="Kicker Manager Spieltag → Firebase")
    parser.add_argument("--spieltag", "-s", type=int, required=True, help="Spieltag-Nummer (z.B. 3)")
    parser.add_argument("--board",    "-b", type=str, required=True, help="Board-ID aus der Transferbrett-URL (?board=...)")
    parser.add_argument("--csv",      type=str, default=None,        help="Lokale CSV-Datei verwenden statt kicker.de zu scrapen")
    parser.add_argument("--dry-run",  action="store_true",           help="Nur anzeigen, nichts in Firebase schreiben")
    args = parser.parse_args()

    # Spieler laden
    if not os.path.exists(PLAYERS_FILE):
        print(f"[Fehler] {PLAYERS_FILE} nicht gefunden. Bitte im selben Ordner wie das Script ablegen.")
        sys.exit(1)
    players = load_players(PLAYERS_FILE)
    print(f"[OK] {len(players)} Spieler geladen.")

    # CSV besorgen
    csv_text = None
    if args.csv:
        print(f"[CSV] Lese lokale Datei: {args.csv}")
        with open(args.csv, encoding="utf-8-sig") as f:
            csv_text = f.read()
    else:
        if not KICKER_USER or not KICKER_PASS:
            print("[Fehler] Zugangsdaten fehlen.")
            print("         Setze KICKER_USER und KICKER_PASS als Umgebungsvariablen oder trage sie oben im Script ein.")
            sys.exit(1)
        session = requests.Session()
        session.headers["User-Agent"] = "Mozilla/5.0 (compatible; TransferbreitBot/1.0)"
        if not kicker_login(session):
            print("[Fehler] Login fehlgeschlagen. Abbruch.")
            sys.exit(1)
        csv_text = download_csv(session, args.spieltag)
        if not csv_text:
            print("[Fehler] CSV-Download fehlgeschlagen.")
            print("         Tipp: Lade die CSV manuell aus dem Kicker-Manager herunter")
            print("         und übergib sie mit: --csv Spieltag3_Noten.csv")
            sys.exit(1)

    # CSV parsen
    rows = parse_csv(csv_text)
    print(f"[OK] {len(rows)} Spieler-Zeilen in CSV gefunden.")
    if not rows:
        sys.exit(1)

    # Spielernamen abgleichen
    matched, unmatched = build_matchday_entry(rows, players)
    print(f"[OK] {len(matched)} Spieler zugeordnet, {len(unmatched)} nicht gefunden.")
    if unmatched:
        print("     Nicht zugeordnet:")
        for r in unmatched:
            print(f"       - {r['name']} ({r['club']})")

    if not matched:
        print("[Fehler] Kein einziger Spieler konnte zugeordnet werden. Abbruch.")
        sys.exit(1)

    entry = {
        "importedAt": int(time.time() * 1000),
        "players":    matched,
    }

    if args.dry_run:
        print("[Dry-Run] Würde folgendes in Firebase schreiben:")
        print(json.dumps(entry, indent=2, ensure_ascii=False)[:500] + " …")
        return

    # Firebase
    success = push_to_firebase(args.board, args.spieltag, entry)
    if success:
        print(f"\n✓ Spieltag {args.spieltag} wurde direkt in Firebase importiert.")
        print(f"  Einfach die Transferbrett-Seite neu laden – der Spieltag ist sofort sichtbar.")
    else:
        print("\nFirebase-Push fehlgeschlagen. CSV wurde aber korrekt geladen und geparst.")
        print("Tipp: Überprüfe die Board-ID oder importiere die CSV manuell im Tool.")


if __name__ == "__main__":
    main()
