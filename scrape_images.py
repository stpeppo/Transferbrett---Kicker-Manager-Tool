#!/usr/bin/env python3
"""
Bilder-Scraper: URL eingeben -> alle Bilder der Seite werden heruntergeladen.

Verwendung:
  python scrape_images.py https://example.com
  python scrape_images.py                      (fragt die URL interaktiv ab)
  python scrape_images.py URL -o ordner --browser --min-size 5000

Optionen:
  -o, --out DIR      Zielordner (Standard: bilder_<domain>)
  --browser          Seite per Playwright (Chromium) laden, z.B. für JavaScript-Seiten
  --min-size BYTES   Kleinere Dateien verwerfen (Standard: 0)

Benötigt:
  pip install requests beautifulsoup4
  (nur mit --browser zusätzlich: pip install playwright && python -m playwright install chromium)
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Fehlende Pakete. Bitte installieren:\n  python -m pip install requests beautifulsoup4")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".avif", ".bmp", ".ico"}
CT_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
          "image/svg+xml": ".svg", "image/avif": ".avif", "image/bmp": ".bmp",
          "image/x-icon": ".ico", "image/vnd.microsoft.icon": ".ico"}


def normalize_url(raw):
    raw = raw.strip()
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        raw = "https://" + raw
    return raw


def fetch_html(url, use_browser):
    if not use_browser:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"}, timeout=30)
        r.raise_for_status()
        return r.text, r.url
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Playwright fehlt:\n  python -m pip install playwright\n  python -m playwright install chromium")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        page = browser.new_context(user_agent=UA, locale="de-DE").new_page()
        page.goto(url, wait_until="networkidle", timeout=45000)
        # Lazy-Loading auslösen
        page.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){"
                      "window.scrollTo(0,y);await new Promise(r=>setTimeout(r,150));}}")
        html, final = page.content(), page.url
        browser.close()
    return html, final


def best_from_srcset(srcset):
    best, best_w = None, -1
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1:
            m = re.match(r"(\d+(?:\.\d+)?)[wx]", bits[1])
            w = float(m.group(1)) if m else 0
        if w >= best_w:
            best, best_w = bits[0], w
    return best


def extract_image_urls(html, base):
    soup = BeautifulSoup(html, "html.parser")
    found = []

    def add(u):
        if u and not u.startswith(("data:", "javascript:", "#")):
            found.append(urljoin(base, u.strip()))

    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            add(img.get(attr))
        for attr in ("srcset", "data-srcset"):
            if img.get(attr):
                add(best_from_srcset(img[attr]))
    for src in soup.find_all("source"):
        for attr in ("srcset", "data-srcset"):
            if src.get(attr):
                add(best_from_srcset(src[attr]))
    for meta in soup.find_all("meta"):
        if (meta.get("property") or meta.get("name") or "") in ("og:image", "twitter:image"):
            add(meta.get("content"))
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or [])
        if "icon" in rel or "image_src" in rel:
            add(link.get("href"))
    for tag in soup.find_all(style=True):
        for u in CSS_URL.findall(tag["style"]):
            add(u)
    for style in soup.find_all("style"):
        for u in CSS_URL.findall(style.get_text()):
            if os.path.splitext(urlparse(u).path)[1].lower() in IMG_EXT:
                add(u)

    seen, unique = set(), []
    for u in found:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def filename_for(url, content_type, used):
    path = unquote(urlparse(url).path)
    name = re.sub(r"[^\w.\-]+", "_", os.path.basename(path)) or "bild"
    stem, ext = os.path.splitext(name)
    if ext.lower() not in IMG_EXT:
        ext = CT_EXT.get(content_type.split(";")[0].strip().lower(), ".img")
    name = stem[:80] + ext
    if name in used:
        name = f"{stem[:70]}_{hashlib.md5(url.encode()).hexdigest()[:6]}{ext}"
    used.add(name)
    return name


def main():
    ap = argparse.ArgumentParser(description="Lädt alle Bilder einer Webseite herunter.")
    ap.add_argument("url", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--browser", action="store_true")
    ap.add_argument("--min-size", type=int, default=0)
    args = ap.parse_args()

    url = normalize_url(args.url or input("Homepage-URL: "))
    host = urlparse(url).netloc.replace(":", "_")
    out = Path(args.out or f"bilder_{host}")

    print(f"Lade {url} ...")
    html, final_url = fetch_html(url, args.browser)
    urls = extract_image_urls(html, final_url)
    print(f"{len(urls)} Bild-URLs gefunden.")
    if not urls:
        print("Nichts gefunden. Bei JavaScript-Seiten --browser versuchen.")
        return

    out.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Referer": final_url})
    used, ok = set(), 0
    for i, u in enumerate(urls, 1):
        try:
            r = session.get(u, timeout=30)
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "")
            if not ct.lower().startswith("image/") and os.path.splitext(urlparse(u).path)[1].lower() not in IMG_EXT:
                print(f"[{i}/{len(urls)}] übersprungen (kein Bild): {u}")
                continue
            if len(r.content) < args.min_size:
                print(f"[{i}/{len(urls)}] übersprungen (zu klein): {u}")
                continue
            name = filename_for(u, ct, used)
            (out / name).write_bytes(r.content)
            ok += 1
            print(f"[{i}/{len(urls)}] {name} ({len(r.content) // 1024} KB)")
        except Exception as e:
            print(f"[{i}/{len(urls)}] Fehler {u}: {e}")

    print(f"\nFertig: {ok} Bilder in {out.resolve()}")


if __name__ == "__main__":
    main()
