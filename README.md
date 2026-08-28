# Transferbrett – Projektuebergabe an Claude Code

Auktions-Board fuer das kicker Managerspiel Classic. Bisher als claude.ai-
Artefakt betrieben unter:
https://claude.ai/code/artifact/6cf831ad-a35a-4c92-bbca-c08b9f1bbbdc

## Dateien

- `transferbrett_template.html` – der eigentliche Quellcode (HTML/CSS/JS in
  einer Datei). Enthaelt die Platzhalter `__STATE_JSON__` und
  `__PLAYERS_JSON__`, die beim Bauen ersetzt werden. **Hier wird entwickelt.**
- `players_slim.json` – die Spielerliste (Name, Verein, Position, Marktwert,
  Punkte/Note Vorsaison). Wird aus einem kicker.de-CSV-Export erzeugt, siehe
  `import_players_csv.py` unten.
- `import_players_csv.py` – wandelt einen kicker.de-Spieler-Export (CSV,
  Semikolon-getrennt, Spalten `ID;Vorname;Nachname;Angezeigter Name (kurz);
  Angezeigter Name;Verein;Position;Marktwert;Punkte;Notendurchschnitt`) in
  `players_slim.json` um. Aufruf: `python3 import_players_csv.py pfad/zur/
  export.csv`. Spieler-IDs bleiben zwischen Exports stabil (z.B.
  `pl-k00030669`), dadurch bleiben bestehende Kaeufe/Bearbeitungen auf
  laufenden Boards nach einem Refresh weiter zuordenbar. Danach
  `build_transferbrett.py` erneut ausfuehren.
- `build_transferbrett.py` – baut `transferbrett.html` aus `transferbrett_
  template.html` + `players_slim.json` mit frischem Startzustand (3 leere
  Teams, kein Admin). Einfach ausfuehren: `python3 build_transferbrett.py`
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
- Kader-Zeilen zeigen die Position (TW/ABW/MF/ST) als Badge vor dem Namen.
- Anwesende koennen sich optional einem Team zuordnen (Dropdown in der
  Anwesenheitsliste); Team-Karte zeigt "Gespielt von: ...". Rein
  informativ, keine Rechtepruefung daran gekoppelt.
- Presence liegt auf einem eigenen Firebase-Pfad, getrennt vom Spielstand
  (Teams/Kaeufe/Verlauf/Admin-Status) -- ein harmloses "ich bin noch da"
  kann so nie mehr Kaeufe oder den Admin-Claim eines anderen ueberschreiben.
- Live-Auktionsmodus: Der Admin startet eine Sitzung mit festem Gebotsschritt.
  Die individuellen Teambudgets und Kontostaende bleiben erhalten. Alle
  angemeldeten Browser mit Teamzuordnung werden als Teilnehmer uebernommen. Eine ausgewaehlte oder
  zufaellige Startperson legt einen unvergebenen Spieler per Drag-and-drop
  oder ueber "Zur Auktion hinzufuegen" auf den virtuellen Auktionsplatz. Der
  Button bleibt fuer alle sichtbar, ist aber nur fuer die Person am Zug aktiv. Danach
  koennen alle Teilnehmer ein eigenes Gebot ab dem sichtbaren Mindestgebot
  eingeben; der Marktwert ist das erste Mindestgebot. Der Admin erteilt den
  Zuschlag; Kauf, Budget und Verlauf werden in derselben Firebase-Transaktion
  aktualisiert und das Nominierungsrecht wandert zur naechsten Person.
- Waehrend einer Live-Auktion sind konkurrierende Direktkaeufe und strukturelle
  Aenderungen gesperrt. Gebote laufen ausschliesslich online und transaktional;
  ein Offline-Fallback wird fuer Auktionen bewusst nicht angeboten.
- Ueber "Spiel verlassen" kann sich ein Browser aktiv und sofort aus der
  Anwesenheit sowie einer laufenden Auktionsreihenfolge entfernen. Bereits
  abgegebene Gebote bleiben gueltig; Nominierungsrecht und gegebenenfalls die
  Adminrolle werden ohne Unterbrechung weitergegeben.
- Die Adminrolle kann auch waehrend einer laufenden Auktion uebernommen oder
  freigegeben werden. Der Wechsel wird unmittelbar per Firebase-Transaktion
  an alle verbundenen Browser verteilt.

## Hosting

Live unter `https://stpeppo.github.io/Transferbrett---Kicker-Manager-Tool/`
(GitHub Pages, `main`-Branch, Root-Ordner; `index.html` leitet auf
`transferbrett.html` weiter). Beim Aufruf ohne `?board=` erscheint eine
lokale Admin-Passwortabfrage. Nach erfolgreicher Eingabe bleibt der jeweilige
Browser via `localStorage` dauerhaft freigegeben. Im ausgelieferten Quellcode
liegt nur ein gesalzener SHA-256-Pruefwert, nicht das Klartextpasswort. Da
GitHub Pages ausschliesslich statische Dateien ausliefert, ist diese Abfrage
eine einfache Zugangshuerde und keine serverseitig erzwungene Authentifizierung.
Danach erscheint eine Startseite: "Neues Spiel starten" (erzeugt einen 5-stelligen Code) oder
"Beitreten" mit einem Code von Freunden. Aktueller Code + "Link kopieren"
stehen im Header. Mitspieler brauchen nur den Link, kein Claude-Zugriff und
kein eigenes Tool. Firebase-Live-Sync wurde bereits in einer echten
Mehr-Geraete-Session bestaetigt (inkl. mobil).

## Testen vor jeder Veroeffentlichung

Bisher wurde jede Aenderung vor dem Veroeffentlichen mit Playwright
(Chromium unter `/opt/pw-browsers/chromium`) durchgetestet – Kaufen,
Admin-Wechsel, Sortierung, Spieler bearbeiten/hinzufuegen/loeschen,
Anwesenheitsliste, Konsole/Seite auf Fehler pruefen. Das sollte bei
Weiterarbeit in Claude Code beibehalten werden.
