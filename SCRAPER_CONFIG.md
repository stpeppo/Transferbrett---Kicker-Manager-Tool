# Scraper Konfiguration – Funktionierende Einstellungen

Stand: 2026-09-21 | Zuletzt getestet mit: Spieltag 1, Saison 2026-27

---

## Voraussetzungen

```bash
pip install flask flask-cors playwright beautifulsoup4
python -m playwright install chromium
```

**Auf Firmen-Laptops (Firewall blockiert SSL-Zertifikate):**
```powershell
$env:NODE_OPTIONS="--use-system-ca"
python -m playwright install chromium
```
Hinweis: `pip` und `playwright` direkt aufrufen schlägt auf Firmen-Rechnern fehl → immer `python -m pip` und `python -m playwright` verwenden.

## Starten

Doppelklick auf **`start.bat`** im Projektordner.  
Das öffnet den Server im Hintergrund und die lokale `transferbrett.html`.

**Wichtig:** Immer die **lokale Datei** öffnen (`transferbrett.html` aus dem Repo), nicht die GitHub Pages-URL – GitHub Pages zeigt die `main`-Branch, die den Scraper-Button nicht enthält.

---

## Kritische Einstellungen (bei Problemen hier zuerst prüfen)

### `headless=False` — PFLICHT

```python
browser = pw.chromium.launch(headless=False)
```

**Warum:** kicker.de nutzt Cloudflare-Bot-Schutz. Mit `headless=True` erkennt Cloudflare den Browser als Bot und blockiert alle Anfragen (`data-cfasync` im HTML). Mit sichtbarem Browser (`headless=False`) funktioniert es.

**Symptom wenn falsch:** Server-Log zeigt `Cloudflare-Challenge erkannt, warte 3s ...` in einer Endlosschleife.

### User-Agent (Windows Chrome nachahmen)

```python
user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
```

### Locale

```python
locale="de-DE"
```

---

## Server

- **Port:** 7431
- **Host:** 127.0.0.1 (nur lokal, kein externer Zugriff)
- **Datei:** `server.py`
- **Endpunkte:**
  - `/scrape?spieltag=X&saison=2026-27` → liefert CSV
  - `/status` → `{"running": true/false}`

---

## Saison-Format

| Saison | Format-String |
|--------|--------------|
| 2025/26 | `2025-26` |
| 2026/27 | `2026-27` |

---

## kicker.de URL-Formate

### Saison 2025-26 (alt)
```
/bundesliga/spieltag/2025-26/X/spiel/.../schema
```

### Saison 2026-27 (neu)
```
/team1-gegen-team2-2026-bundesliga-ID/analyse
```
Der Scraper erkennt beide Formate automatisch. Beim neuen Format wird `/analyse` durch `/schema` ersetzt.

---

## Spielerliste (Positionen)

Datei: `players-se-k00012026.csv`  
Wird benötigt für die Positionszuordnung (Torwart/Abwehr/Mittelfeld/Sturm), die den Punktekoeffizienten für Tore bestimmt.

Ohne diese Datei werden alle Spieler als `FORWARD` behandelt (niedrigster Torkoeffizient = 3).

---

## Punktevergabe

Entspricht kicker Interactive:

| Kategorie | Punkte |
|-----------|--------|
| Startelf | +4 |
| Einwechslung | +2 |
| Note-Punkte | `round((3.5 - Note) * 4)` |
| Tor (Torwart) | +6 |
| Tor (Abwehr) | +5 |
| Tor (Mittelfeld) | +4 |
| Tor (Sturm) | +3 |
| Vorlage | +2 |
| Spieler des Spiels | +3 |
| Clean Sheet (TW, nur Startelf) | +2 |
| Rote Karte | -6 |
| Gelb-Rote Karte | -3 |
| Unbesetzte Formations-Position (weniger als 11 eigene Spieler kamen zum Einsatz) | -10 pro Position |

Die -10-Punkte-Regel wird nicht vom Scraper geliefert, sondern automatisch im Tool berechnet (`teamMatchdayResult` in `transferbrett_template.html`): für jeden der 11 Formations-Plätze, der nicht mit einem tatsächlich eingesetzten eigenen Spieler besetzt werden kann, werden 10 Punkte abgezogen.

---

## Bekannte Probleme & Lösungen

| Problem | Ursache | Lösung |
|---------|---------|--------|
| `Cloudflare-Challenge erkannt` (Endlosschleife) | `headless=True` | `headless=False` setzen |
| `0 Spiele gefunden` | Neues URL-Format der Saison | elif-Branch für `-bundesliga-\d+$` in `get_game_links` |
| Button `Von kicker.de laden` nicht sichtbar | GitHub Pages zeigt `main`-Branch | Lokale `transferbrett.html` öffnen (per `start.bat`) |
| Dialog verschwindet beim Tippen | Modal falsch im DOM eingehängt | `backdrop.appendChild(modal)` → dann `modalRoot.appendChild(backdrop)` |

---

## Fehlerbehebungs-Checkliste

Wenn etwas nicht funktioniert, was vorher funktioniert hat:

1. **Vergleich mit letztem funktionierendem Zustand** – was hat sich geändert?
2. `headless=False` in `server.py`?
3. Lokale HTML-Datei (nicht GitHub Pages)?
4. Server läuft? → `curl http://localhost:7431/status`
5. Neues URL-Format auf kicker.de? → Debug-Output prüfen: `DEBUG: X hrefs total`
6. Cloudflare-Challenge? → Debug-Output prüfen: `data-cfasync` im HTML
