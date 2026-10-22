@echo off
:: Bilder-Scraper: URL eingeben, alle Bilder werden heruntergeladen
cd /d "%~dp0"
python scrape_images.py %*
if %ERRORLEVEL% neq 0 echo Fehler beim Ausfuehren.
pause
