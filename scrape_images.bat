@echo off
:: Bilder-Scraper: URL eingeben, alle Bilder werden heruntergeladen (Browser-Modus, auch fuer JS-Seiten)
cd /d "%~dp0"
python scrape_images.py %* --browser
if %ERRORLEVEL% neq 0 echo Fehler beim Ausfuehren.
pause
