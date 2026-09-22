# Installation – Transferbrett Kicker-Manager-Tool

Dieses Dokument hält fest, welche Tools benötigt werden und wie das Projekt auf
einem neuen Rechner aufgesetzt wird. Ziel ist es, daraus später automatisierte
Installer zu bauen.

---

## Übersicht

Das Tool besteht aus:

| Schicht | Technologie | Zweck |
|---------|-------------|-------|
| App | HTML + CSS + JS (eine Datei) | Browser-App, kein Server nötig |
| Build | Python 3 | `build_transferbrett.py`, `import_players_csv.py` |
| Tests (Unit) | Node.js (node:test, built-in) | `auction_logic.test.js`, `auction_build_integration.test.js` |
| Tests (E2E) | Playwright + Chromium | Browser-Tests (live-auction.tdd.md) |
| Hosting | GitHub Pages | statisch, kein eigener Server |
| Echtzeit-Sync | Firebase Realtime Database | externer Dienst, kein lokales Setup |

---

## Windows – Schritt für Schritt

### 1. Git

**Download:** https://git-scm.com/download/win  
Installer ausführen, Standardoptionen sind ausreichend.

```
git --version   # Prüfen ob Installation funktioniert hat
```

### 2. Python 3

**Download:** https://www.python.org/downloads/windows/  
Empfohlen: Python 3.11 oder neuer.

> **Wichtig beim Installer:** Haken bei **"Add Python to PATH"** setzen!

```
python --version   # Prüfen
```

Python-Abhängigkeiten: **keine externen Pakete nötig** – nur die Standard-Library
(`json`, `csv`, `sys`).

### 3. Node.js

Wird für die Unit-Tests benötigt (`node:test` ist in Node.js 18+ eingebaut).

**Download:** https://nodejs.org/en/download  
Empfohlen: LTS-Version (18 oder neuer).

```
node --version   # Prüfen
```

Externe npm-Pakete: **keine** – Tests verwenden nur Built-ins.

### 4. Playwright + Chromium (für E2E-Tests)

Nur nötig wenn E2E-Tests lokal ausgeführt werden sollen.

```
npm init -y
npm install --save-dev @playwright/test
npx playwright install chromium
```

### 5. Repository klonen

```
git clone https://github.com/stpeppo/Transferbrett---Kicker-Manager-Tool.git
cd Transferbrett---Kicker-Manager-Tool
```

### 6. App bauen

```
python build_transferbrett.py
```

Erzeugt `transferbrett.html` – diese Datei direkt im Browser öffnen.

### 7. Unit-Tests ausführen

```
node --test tests/auction_logic.test.js
node --test tests/auction_build_integration.test.js
```

---

## Linux – Schritt für Schritt

### 1. Git

```bash
# Debian/Ubuntu
sudo apt install git

# Fedora/RHEL
sudo dnf install git
```

### 2. Python 3

```bash
# Debian/Ubuntu
sudo apt install python3

# Fedora/RHEL
sudo dnf install python3
```

Externe Pakete: **keine**.

### 3. Node.js

```bash
# Debian/Ubuntu (LTS via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install nodejs

# Fedora/RHEL
sudo dnf install nodejs
```

### 4. Playwright + Chromium (für E2E-Tests)

```bash
npm init -y
npm install --save-dev @playwright/test
npx playwright install chromium
```

> Auf diesem Projekt-Server liegt Chromium unter `/opt/pw-browsers/chromium`
> (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers). Lokal ist `npx playwright install chromium`
> der normale Weg.

### 5. Repository klonen

```bash
git clone https://github.com/stpeppo/Transferbrett---Kicker-Manager-Tool.git
cd Transferbrett---Kicker-Manager-Tool
```

### 6. App bauen und testen

```bash
python3 build_transferbrett.py
node --test tests/auction_logic.test.js
node --test tests/auction_build_integration.test.js
```

---

## Firebase (optional, für Live-Sync)

Firebase ist ein externer Dienst – kein lokales Setup nötig.  
Konfiguration liegt eingebettet im `transferbrett_template.html`.  
Fällt die Firebase-Verbindung weg, greift die App automatisch auf `localStorage` zurück.

Für eigene Firebase-Projekte:
1. Firebase-Konto anlegen unter https://console.firebase.google.com
2. Realtime Database erstellen
3. Konfigurationsblock im Template anpassen (`firebaseConfig`-Objekt)

---

## Schnellübersicht – benötigte Tools

| Tool | Version (Minimum) | Pflicht | Zweck |
|------|-------------------|---------|-------|
| Git | beliebig | Ja | Repository klonen/pushen |
| Python | 3.8+ | Ja | App bauen, CSV importieren |
| Node.js | 18+ | Ja | Unit-Tests |
| npm | kommt mit Node | Nur für E2E | Playwright installieren |
| Playwright + Chromium | beliebig | Nein* | E2E-Browser-Tests |

*Empfohlen vor jedem Release – wird im Projekt so praktiziert.

---

## Geplant: Installer

- [ ] **Windows:** PowerShell-Skript (`install.ps1`) – prüft/installiert Git, Python, Node; klont Repo; führt Build aus
- [ ] **Linux:** Shell-Skript (`install.sh`) – gleiches Vorgehen via apt/dnf
- [ ] Beide Skripte sollen am Ende `transferbrett.html` fertig gebaut im Browser öffnen

---

*Zuletzt aktualisiert: 2026-09-22*
