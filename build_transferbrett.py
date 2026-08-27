"""
Baut transferbrett.html aus transferbrett_template.html + players_slim.json.

Setzt einen frischen Startzustand ein (3 leere Teams, kein Admin, keine Kaeufe/
Historie/Anwesenheit). Bei jeder inhaltlichen Aenderung am Template einfach
erneut ausfuehren:

    python3 build_transferbrett.py
"""
import json

TEMPLATE = "transferbrett_template.html"
PLAYERS = "players_slim.json"
OUT = "transferbrett.html"

with open(TEMPLATE, encoding="utf-8") as f:
    tpl = f.read()
with open(PLAYERS, encoding="utf-8") as f:
    players_json = f.read()

teams = [
    {"id": "team%d" % i, "name": "Team %d" % i, "budget": 100, "balance": 100, "formation": None}
    for i in range(1, 4)
]
state = json.dumps(
    {
        "teams": teams,
        "purchases": {},
        "adminToken": None,
        "history": [],
        "playerEdits": {},
        "customPlayers": [],
        "deletedPlayers": [],
        "presence": {},
    },
    ensure_ascii=False,
)

out = tpl.replace("__STATE_JSON__", state).replace("__PLAYERS_JSON__", players_json)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(out)

print("built", OUT, "-", len(out), "bytes")
