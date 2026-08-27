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
- `transferbrett.html` – die fertig gebaute, eigenstaendige Offline-Datei
  (kann direkt im Browser geoeffnet werden; speichert dann nur lokal).

## Funktionsstand (26./27.08.2026)

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

## Offene Idee, noch nicht umgesetzt

Umbau auf eine **eigene Firebase Realtime Database** statt der
claude.ai-Artefakt-Speicherung, damit das Tool auch ausserhalb von
claude.ai (z.B. GitHub Pages/Netlify) mit echtem geteiltem Live-Stand
laeuft. Naechste Schritte dafuer:

1. Kostenloses Firebase-Projekt anlegen, Realtime Database aktivieren.
2. `persist()`/das Laden der `STATE` im Template auf die Firebase JS-SDK
   umstellen (ersetzt `window.claude.use('artifact')`).
3. `transferbrett.html` irgendwo statisch hosten (GitHub Pages, Netlify, …).

## Testen vor jeder Veroeffentlichung

Bisher wurde jede Aenderung vor dem Veroeffentlichen mit Playwright
(Chromium unter `/opt/pw-browsers/chromium`) durchgetestet – Kaufen,
Admin-Wechsel, Sortierung, Spieler bearbeiten/hinzufuegen/loeschen,
Anwesenheitsliste, Konsole/Seite auf Fehler pruefen. Das sollte bei
Weiterarbeit in Claude Code beibehalten werden.
