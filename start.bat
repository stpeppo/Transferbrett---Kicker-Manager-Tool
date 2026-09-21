@echo off
:: Transferbrett – Scraper-Server starten + Tool im Browser öffnen

:: Pfad zu diesem Skript als Arbeitsverzeichnis setzen
cd /d "%~dp0"

:: Prüfen ob server.py bereits läuft
curl -s --max-time 1 http://localhost:7431/status >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo Server läuft bereits auf Port 7431.
) else (
    echo Starte Scraper-Server...
    start "" /min python server.py
    :: Kurz warten bis der Server hochgefahren ist
    timeout /t 3 /nobreak >nul
)

:: Transferbrett im Standard-Browser öffnen
:: GitHub Pages URL – passe sie ggf. an:
start "" "https://stpeppo.github.io/Transferbrett---Kicker-Manager-Tool/transferbrett.html"

:: Alternativ: lokale Datei öffnen (Kommentar entfernen wenn kein GitHub Pages genutzt wird)
:: start "%~dp0transferbrett.html"

exit /b
