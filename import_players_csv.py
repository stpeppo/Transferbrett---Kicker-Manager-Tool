"""
Wandelt einen kicker.de-Spieler-Export (CSV, Semikolon-getrennt) in players_slim.json um.

Erwartete Spalten (Kopfzeile):
ID;Vorname;Nachname;Angezeigter Name (kurz);Angezeigter Name;Verein;Position;Marktwert;Punkte;Notendurchschnitt

Aufruf:
    python3 import_players_csv.py pfad/zur/exportierten-datei.csv

Schreibt players_slim.json neu. Anschliessend build_transferbrett.py erneut
ausfuehren, um transferbrett.html neu zu bauen.
"""
import csv
import json
import sys

POS_MAP = {
    "GOALKEEPER": "TW",
    "DEFENDER": "ABW",
    "MIDFIELDER": "MF",
    "FORWARD": "ST",
}

OUT = "players_slim.json"


def convert(csv_path):
    players = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            pos = POS_MAP.get(row["Position"])
            if pos is None:
                raise ValueError("Unbekannte Position: %r (Spieler %s)" % (row["Position"], row.get("ID")))
            pts = int(row["Punkte"])
            note = float(row["Notendurchschnitt"])
            players.append({
                "id": row["ID"],
                "n": row["Angezeigter Name"],
                "k": row["Angezeigter Name (kurz)"],
                "c": row["Verein"],
                "p": pos,
                "v": int(row["Marktwert"]),
                "pt": pts,
                "no": note,
                "new": 1 if (pts == 0 and note == 0.0) else 0,
            })
    return players


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Aufruf: python3 import_players_csv.py pfad/zur/exportierten-datei.csv")
        sys.exit(1)
    players = convert(sys.argv[1])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(players, f, ensure_ascii=False, separators=(",", ":"))
    print("geschrieben:", OUT, "-", len(players), "Spieler")
