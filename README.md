# Transferbrett – Projektuebergabe an Claude Code

Auktions-Board fuer das kicker Managerspiel Classic. Bisher als claude.ai-
Artefakt betrieben unter:
https://claude.ai/code/artifact/6cf831ad-a35a-4c92-bbca-c08b9f1bbbdc

## Dateien

- `transferbrett_template.html` – der eigentliche Quellcode (HTML/CSS/JS in
  einer Datei). Enthaelt die Platzhalter `__STATE_JSON__` und
  `__PLAYERS_JSON__`, die beim Bauen ersetzt werden. **Hier wird entwickelt.**
- `players_slim.json` – die 564 Spieler (Name, Verein, Position, Marktwert,
  Punkte/Note Vorsaison, ausgewaehlte Torschuetzen-Statistiken).
- `build_transferbrett.py` – baut `transferbrett.html` aus den beiden
  obigen Dateien mit frischem Startzustand (3 leere Teams, kein Admin).
  Einfach ausfuehren: `python3 build_transferbrett.py`
- `transferbrett.html` – die fertig gebaute, eigenstaendige Datei (kann
  direkt im Browser geoeffnet oder statisch gehostet werden).

## Funktionsstand (26.-27.08.2026)

- Auktions-Kauf mit Team-Budgets, Undo, Team-zu-Team-Handel (Verkaeufer
  bekommt vollen neuen Verkaufspreis gutgeschrieben, kann ueber Startbudget
  landen).
- Verlaufsprotokoll als eigene Ansicht, jeder Eintrag rueckgaengig machbar
  oder neu zuordenbar.
- Admin-System: nur ein aktiver Admin darf kaufen/aendern/speichern, Rest
  darf suchen/filtern/zusehen.
- Zuruecksetzen-Button (nur Admin) mit Sicherheitsabfrage + Export-Option.
- Spieler bearbeiten (Position/Marktwert), hinzufuegen, loeschen (nur Admin,
  Loeschen blockiert bei bereits verkauften Spielern).
- Sortierbare Spaltenkoepfe (Position, Marktwert, Punkte, Note) inkl.
  Klick-Toggle und Pfeil-Indikator, synchron zum bestehenden Sortier-Dropdown.
- "Flutlicht"-Farbkonzept: kraeftige, stimmungsvolle Palette in Hell- und
  Dunkelmodus (Gruen/Gold/Crimson/Violett).
- Anwesenheitsliste: jeder traegt einmal seinen Namen ein, alle sehen wer
  zuletzt aktiv war; Admin wird namentlich angezeigt statt nur "jemand
  anderes".
- Formation je Team waehlbar (3-4-3, 3-5-2, 4-3-3, 4-4-2, 4-5-1, 5-3-2,
  5-4-1) mit Ist/Soll-Anzeige je Position basierend auf dem Kader.
- **Geteilter Live-Stand ueber Firebase Realtime Database** statt
  claude.ai-Artefakt-Speicherung: jeder Browser verbindet sich direkt mit
  derselben Datenbank, kein eigener Server, kein Claude-Zugriff noetig.
  Faellt automatisch auf reines `localStorage` zurueck, wenn Firebase nicht
  erreichbar ist. Mehrere gleichzeitige Boards moeglich ueber
  `?board=<name>` in der URL (Standard: `default`).
- Export laeuft jetzt als normaler Browser-Download (Blob + `<a download>`)
  statt ueber die claude.ai-Downloads-Capability.

## Naechster Schritt: Hosting

`transferbrett.html` ist noch nicht oeffentlich erreichbar. Empfehlung:
**GitHub Pages** fuer dieses Repo aktivieren (Settings -> Pages -> Source:
Deploy from branch -> `main`). Danach ist die Datei unter
`https://stpeppo.github.io/Transferbrett---Kicker-Manager-Tool/transferbrett.html`
erreichbar (kein `index.html` vorhanden, daher der volle Dateiname in der
URL). Mitspieler brauchen dann nur diesen Link, kein Claude-Zugriff und
kein eigenes Tool.

**Wichtig:** Die Firebase-Live-Sync konnte bisher nicht Ende-zu-Ende in
einer echten Browser-Session gegen das echte Projekt getestet werden (die
Entwicklungsumgebung, in der dieser Code entstand, hat keinen Zugriff auf
Google-/Firebase-Domains). Vor dem ersten echten Spielabend unbedingt mit
zwei parallel geoeffneten Browserfenstern (gleicher `?board=`-Wert)
gegentesten.

## Testen vor jeder Veroeffentlichung

Bisher wurde jede Aenderung vor dem Veroeffentlichen mit Playwright
(Chromium unter `/opt/pw-browsers/chromium`) durchgetestet – Kaufen,
Admin-Wechsel, Sortierung, Spieler bearbeiten/hinzufuegen/loeschen,
Anwesenheitsliste, Konsole/Seite auf Fehler pruefen. Das sollte bei
Weiterarbeit in Claude Code beibehalten werden.
