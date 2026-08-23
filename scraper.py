import os
import re
import json
import time
import logging
import subprocess
from datetime import datetime
import requests as req_lib

# ── Sabitler ──────────────────────────────────────────
STREAM_WAIT    = 6       # Network izleme süresi (saniye)
BODY_WAIT      = 6       # Sayfa yükleme bekleme
POLL_INTERVAL  = 0.5     # Log kontrol aralığı
DOMAIN_TIMEOUT = 3       # Domain tarama timeout
MIN_NUMBER     = 49
MAX_NUMBER     = 75
DOMAIN_BASE    = "mahsunsports"
DOMAIN_TLD     = "xyz"
OUTPUT_FILE    = "playlist.m3u"
STATS_FILE     = "stats.json"

# ── Logging ───────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            f"logs/scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("selenium").setLevel(logging.ERROR)

# ═══════════════════════════════════════════════════════
#  SELENIUM - Wire opsiyonel
# ═══════════════════════════════════════════════════════
try:
    from seleniumwire import webdriver
    WIRE = True
    log.info("✅ SeleniumWire aktif")
    logging.getLogger("seleniumwire").setLevel(logging.ERROR)
    logging.getLogger("hpack").setLevel(logging.ERROR)
except ImportError:
    from selenium import webdriver
    WIRE = False
    log.info("ℹ️ SeleniumWire yok, standart selenium kullanılacak")

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ═══════════════════════════════════════════════════════
#  BASE URL OTOMATİK BUL
# ═══════════════════════════════════════════════════════
def generate_domains():
    return [f"https://{DOMAIN_BASE}{i}.{DOMAIN_TLD}" for i in range(MIN_NUMBER, MAX_NUMBER + 1)]


def find_base_url():
    session = req_lib.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    log.info(f"🔎 Domain taranıyor: {DOMAIN_BASE}{MIN_NUMBER}.{DOMAIN_TLD} → {DOMAIN_BASE}{MAX_NUMBER}.{DOMAIN_TLD}")

    for domain in generate_domains():
        try:
            resp = session.get(domain, headers=headers, timeout=DOMAIN_TIMEOUT, allow_redirects=False)
            if resp.status_code in (200, 301, 302, 303, 307, 308):
                final_url = domain.rstrip("/")
                log.info(f"  ✅ Aktif domain bulundu: {final_url} (HTTP {resp.status_code})")
                return final_url
        except Exception:
            pass

    log.warning("⚠️ Çalışan domain bulunamadı, varsayılan kullanılıyor.")
    return f"https://{DOMAIN_BASE}49.{DOMAIN_TLD}"


BASE_URL = find_base_url()
log.info(f"🌐 BASE_URL: {BASE_URL}")


# ═══════════════════════════════════════════════════════
#  TARANACAK SAYFALAR
# ═══════════════════════════════════════════════════════
PAGES = [
    {"slug": "event.html?id=androstreamlivebs1",     "name": "BeIN Sports 1",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivebs2",     "name": "BeIN Sports 2",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivebs3",     "name": "BeIN Sports 3",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivebs4",     "name": "BeIN Sports 4",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivebs5",     "name": "BeIN Sports 5",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivebsm1",    "name": "BeIN Sports Max 1",  "group": "Spor"},
    {"slug": "event.html?id=androstreamlivebsm2",    "name": "BeIN Sports Max 2",  "group": "Spor"},
    {"slug": "event.html?id=androstreamlivess1",     "name": "S Sport",            "group": "Spor"},
    {"slug": "event.html?id=androstreamlivess2",     "name": "S Sport 2",          "group": "Spor"},
    {"slug": "event.html?id=androstreamlivessplus1", "name": "S Sport Plus",       "group": "Spor"},
    {"slug": "event.html?id=androstreamlivets",      "name": "Tivibu Spor",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivets1",     "name": "Tivibu Spor 1",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivets2",     "name": "Tivibu Spor 2",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivets3",     "name": "Tivibu Spor 3",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivets4",     "name": "Tivibu Spor 4",      "group": "Spor"},
    {"slug": "event.html?id=androstreamlivesm1",     "name": "Smart Spor 1",       "group": "Spor"},
    {"slug": "event.html?id=androstreamlivesm2",     "name": "Smart Spor 2",       "group": "Spor"},
    {"slug": "event.html?id=androstreamlivees1",     "name": "Euro Sport 1",       "group": "Spor"},
    {"slug": "event.html?id=androstreamlivees2",     "name": "Euro Sport 2",       "group": "Spor"},
    {"slug": "event.html?id=androstreamliveidm",     "name": "iDMAN Tv",           "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetrts",    "name": "TRT Spor",           "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetrtsy",   "name": "TRT Spor Yıldız",    "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetrts1",   "name": "TRT 1",              "group": "Genel"},
    {"slug": "event.html?id=androstreamliveatv",     "name": "Atv",                "group": "Genel"},
    {"slug": "event.html?id=androstreamliveas",      "name": "A Spor",             "group": "Spor"},
    {"slug": "event.html?id=androstreamlivea2",      "name": "A2",                 "group": "Genel"},
    {"slug": "event.html?id=androstreamlivetjk",     "name": "Tjk Tv",             "group": "Spor"},
    {"slug": "event.html?id=androstreamliveht",      "name": "Ht Spor",            "group": "Spor"},
    {"slug": "event.html?id=androstreamlivenba",     "name": "NBA Tv",             "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetv8",     "name": "TV8",                "group": "Genel"},
    {"slug": "event.html?id=androstreamlivetv85",    "name": "TV8,5",              "group": "Genel"},
    {"slug": "event.html?id=androstreamlivetb",      "name": "Tabi Spor",          "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb1",     "name": "Tabi Spor 1",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb2",     "name": "Tabi Spor 2",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb3",     "name": "Tabi Spor 3",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb4",     "name": "Tabi Spor 4",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb5",     "name": "Tabi Spor 5",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb6",     "name": "Tabi Spor 6",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb7",     "name": "Tabi Spor 7",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivetb8",     "name": "Tabi Spor 8",        "group": "Spor"},
    {"slug": "event.html?id=androstreamlivefb",      "name": "FB Tv",              "group": "Spor"},
    {"slug": "event.html?id=androstreamlivegs",      "name": "GS Tv",              "group": "Spor"},
    {"slug": "event.html?id=androstreamlivecbcs",    "name": "CBC Sport",          "group": "Spor"},
    {"slug": "event.html?id=androstreamlivesptstv",  "name": "Sports Tv",          "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn",     "name": "Exxen Tv",           "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn1",    "name": "Exxen Sports 1",     "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn2",    "name": "Exxen Sports 2",     "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn3",    "name": "Exxen Sports 3",     "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn4",    "name": "Exxen Sports 4",     "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn5",    "name": "Exxen Sports 5",     "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn6",    "name": "Exxen Sports 6",     "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn7",    "name": "Exxen Sports 7",     "group": "Spor"},
    {"slug": "event.html?id=androstreamliveexn8",    "name": "Exxen Sports 8",     "group": "Spor"},
]


# ═══════════════════════════════════════════════════════
#  YARDIMCI: URL TEMİZLEME VE KONTROL
# ═══════════════════════════════════════════════════════
def clean_m3u8(url):
    """Linkleri ters slash, boşluk ve HTML varlıklarından arındırır."""
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip().strip('"\'')
    url = url.replace('\\/', '/')
    url = url.replace('&amp;', '&')

    # Gerçek URL bloğunu yakala
    match = re.search(r'https?://[^\s\'"<>]+?\.m3u8(?:\?[^\s\'"<>]*)?', url, re.IGNORECASE)
    if match:
        return match.group(0)
    
    if ".m3u8" in url.lower():
        return url
    return None


def is_m3u8(url):
    return clean_m3u8(url) is not None


# ═══════════════════════════════════════════════════════
#  M3U VE JSON DOSYALARINI GÜNCELLEME (CANLI KAYIT)
# ═══════════════════════════════════════════════════════
def save_playlist(channels, elapsed=0):
    """Her yeni kanal bulunduğunda dosyayı anında günceller."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "#EXTM3U\n",
        f"## Site       : {BASE_URL}\n",
        f"## Güncelleme : {now}\n",
        f"## Toplam     : {len(channels)} kanal\n"
    ]
    for ch in channels:
        lines.append(f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ch["group"]}",{ch["name"]}\n')
        lines.append(f'{ch["url"]}\n')

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "site": BASE_URL,
            "last_update": datetime.now().isoformat(),
            "total_channels": len(channels),
            "duration_sec": elapsed,
            "channels": channels
        }, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════
#  DRIVER AYARLARI
# ═══════════════════════════════════════════════════════
def get_driver():
    log.info("🔧 Driver başlatılıyor...")

    options = Options()
    options.page_load_strategy = "eager"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if not WIRE:
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    service = Service()
    if WIRE:
        driver = webdriver.Chrome(
            service=service,
            options=options,
            seleniumwire_options={"verify_ssl": False, "suppress_connection_errors": True}
        )
    else:
        driver = webdriver.Chrome(service=service, options=options)

    driver.set_page_load_timeout(15)
    log.info("✅ Driver hazır")
    return driver


def close_popups_and_play(driver):
    try:
        driver.execute_script("""
            const closeSels = ['.close', '.popup-close', '#close', '[aria-label="Close"]', '.btn-close'];
            closeSels.forEach(s => document.querySelectorAll(s).forEach(el => el.click()));
            
            const playSels = ['.play-button', '.btn-play', '#play-button', '.jw-icon-playback', '.vjs-play-button'];
            for (let s of playSels) {
                let el = document.querySelector(s);
                if (el) { el.click(); break; }
            }
            document.querySelectorAll('video').forEach(v => {
                try { v.muted = true; v.play(); } catch(e){}
            });
        """)
    except Exception:
        pass


def find_in_js(driver):
    try:
        result = driver.execute_script("""
            var found = null;
            document.querySelectorAll('video, source').forEach(function(el) {
                if (!found && el.src && el.src.indexOf('.m3u8') !== -1) found = el.src;
                if (!found && el.currentSrc && el.currentSrc.indexOf('.m3u8') !== -1) found = el.currentSrc;
            });
            if (found) return found;

            try {
                if (window.hls && window.hls.url) return window.hls.url;
            } catch(e) {}

            try {
                var jw = jwplayer();
                if (jw && jw.getPlaylistItem()) return jw.getPlaylistItem().file;
            } catch(e) {}

            var m = document.documentElement.innerHTML.match(/https?:\\\\?\\/\\\\?\\/[^\\s'\"<>]+\\.m3u8(?:\\?[^\\s'\"<>]*)?/i);
            return m ? m[0] : null;
        """)
        return clean_m3u8(result)
    except Exception:
        return None


def handle_iframes(driver):
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for idx, iframe in enumerate(iframes):
            try:
                driver.switch_to.frame(iframe)
                close_popups_and_play(driver)
                url = find_in_js(driver)
                driver.switch_to.default_content()
                if url:
                    return url
            except Exception:
                driver.switch_to.default_content()
    except Exception:
        pass
    return None


def scrape_page(driver, page):
    url = f"{BASE_URL}/{page['slug']}"
    log.info(f"\n🔍 {page['name']} aranıyor...")

    if WIRE:
        try:
            del driver.requests
        except Exception:
            pass

    try:
        driver.get(url)
        WebDriverWait(driver, BODY_WAIT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        log.warning(f"  ⚠️ Sayfa gecikmesi: {e}")

    time.sleep(0.5)
    close_popups_and_play(driver)

    # 1. JS Kontrolü
    m3u8_url = find_in_js(driver)

    # 2. Network İzleme
    if not m3u8_url:
        deadline = time.time() + STREAM_WAIT
        while time.time() < deadline and not m3u8_url:
            if WIRE:
                try:
                    for r in reversed(driver.requests):
                        cleaned = clean_m3u8(r.url)
                        if cleaned:
                            m3u8_url = cleaned
                            break
                except Exception:
                    pass
            if not m3u8_url:
                time.sleep(POLL_INTERVAL)

    # 3. Iframe Kontrolü
    if not m3u8_url:
        m3u8_url = handle_iframes(driver)

    if m3u8_url:
        log.info(f"  ✅ BULUNDU: {m3u8_url}")
    else:
        log.warning(f"  ❌ M3U8 bulunamadı!")

    return m3u8_url


# ═══════════════════════════════════════════════════════
#  MAIN DÖNGÜSÜ
# ═══════════════════════════════════════════════════════
def main():
    log.info("=" * 55)
    log.info("   M3U8 Scraper Başlatıldı")
    log.info(f"   Base URL : {BASE_URL}")
    log.info(f"   Toplam   : {len(PAGES)} sayfa")
    log.info("=" * 55)

    start = time.time()
    driver = None
    channels = []

    try:
        driver = get_driver()

        for i, page in enumerate(PAGES, 1):
            log.info(f"[{i}/{len(PAGES)}] İşleniyor: {page['name']}")
            m3u8_url = scrape_page(driver, page)

            if m3u8_url:
                channels.append({
                    "name": page["name"],
                    "url": m3u8_url,
                    "group": page["group"],
                })
                # 🔥 ANLIK KAYIT: Her bulunan kanal anında diske yazılır
                save_playlist(channels, elapsed=round(time.time() - start, 1))

            time.sleep(0.3)

    except Exception as e:
        log.error(f"❌ Beklenmedik Hata: {e}", exc_info=True)

    finally:
        if driver:
            try:
                driver.quit()
                log.info("🔒 Driver kapatıldı")
            except Exception:
                pass

    elapsed = round(time.time() - start, 1)
    save_playlist(channels, elapsed=elapsed)

    log.info(f"\n{'='*55}")
    log.info(f"🏁 Bitti! Toplam: {len(channels)} / {len(PAGES)} kanal yazıldı.")
    log.info(f"📁 Dosya: {OUTPUT_FILE}")
    log.info(f"⏱️ Süre : {elapsed}s")
    log.info(f"{'='*55}")


if __name__ == "__main__":
    main()
