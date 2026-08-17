import os
import re
import json
import time
import logging
import subprocess
from datetime import datetime
import requests as req_lib

# ── Sabitler ──────────────────────────────────────────
STREAM_WAIT    = 5       # Network izleme süresi (saniye)
BODY_WAIT      = 6       # Sayfa yükleme bekleme
POLL_INTERVAL  = 0.5     # Log kontrol aralığı
DOMAIN_TIMEOUT = 3       # Domain tarama timeout
MIN_NUMBER     = 45
MAX_NUMBER     = 75
DOMAIN_BASE    = "mahsunsports"
DOMAIN_TLD     = "xyz"
OUTPUT_FILE    = "playlist.m3u"
STATS_FILE     = "stats.json"
CHROMEDRIVER   = os.environ.get("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")
CHROME_BIN     = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome")

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
    log.info("ℹ️ SeleniumWire yok, performans logları kullanılacak")

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ═══════════════════════════════════════════════════════
#  BASE URL OTOMATİK BUL
# ═══════════════════════════════════════════════════════
def generate_domains():
    domains = []
    for i in range(MIN_NUMBER, MAX_NUMBER + 1):
        domains.append(f"https://{DOMAIN_BASE}{i}.{DOMAIN_TLD}")
    return domains


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
            resp = session.get(
                domain,
                headers=headers,
                timeout=DOMAIN_TIMEOUT,
                allow_redirects=False
            )
            if resp.status_code in (200, 301, 302, 303, 307, 308):
                final_url = domain.rstrip("/")
                log.info(f"  ✅ Aktif domain bulundu: {final_url} (HTTP {resp.status_code})")
                return final_url
        except Exception:
            pass

    log.warning("⚠️ Çalışan domain bulunamadı, varsayılan kullanılıyor.")
    return f"https://{DOMAIN_BASE}35.{DOMAIN_TLD}"


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
#  CHROMEDRIVER OTOMATİK BUL
# ═══════════════════════════════════════════════════════
def find_chromedriver():
    env_path = os.environ.get("CHROMEDRIVER_PATH", "")
    if env_path and os.path.exists(env_path):
        log.info(f"✅ Chromedriver (env): {env_path}")
        return env_path

    known = [
        "/usr/local/bin/chromedriver",
        "/usr/bin/chromedriver",
        "/snap/bin/chromedriver",
    ]
    for p in known:
        if os.path.exists(p):
            log.info(f"✅ Chromedriver: {p}")
            return p

    try:
        r = subprocess.run(["which", "chromedriver"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            path = r.stdout.strip()
            log.info(f"✅ Chromedriver (which): {path}")
            return path
    except Exception:
        pass

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        path = ChromeDriverManager().install()
        log.info(f"✅ Chromedriver (wdm): {path}")
        return path
    except Exception as e:
        log.warning(f"⚠️ webdriver-manager: {e}")

    log.error("❌ Chromedriver bulunamadı!")
    return None


def find_chrome_binary():
    env_path = os.environ.get("CHROME_BIN", "")
    if env_path and os.path.exists(env_path):
        return env_path

    known = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/opt/google/chrome/chrome",
    ]
    for p in known:
        if os.path.exists(p):
            log.info(f"✅ Chrome: {p}")
            return p

    try:
        r = subprocess.run(["which", "google-chrome"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass

    return None


# ═══════════════════════════════════════════════════════
#  YARDIMCI
# ═══════════════════════════════════════════════════════
def is_m3u8(url):
    if not url or not isinstance(url, str):
        return False
    lower = url.lower()
    return lower.endswith(".m3u8") or ".m3u8?" in lower


# ═══════════════════════════════════════════════════════
#  DRIVER
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
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-web-security")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Resimleri / fontları kapat → hız kazanç
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Performance log (Wire yoksa)
    if not WIRE:
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    # Chrome binary
    chrome_bin = find_chrome_binary()
    if chrome_bin:
        options.binary_location = chrome_bin
        log.info(f"🌐 Chrome: {chrome_bin}")

    # Chromedriver
    driver_path = find_chromedriver()

    try:
        if driver_path:
            service = Service(executable_path=driver_path)
            log.info(f"🔧 Driver path: {driver_path}")
        else:
            service = Service()

        if WIRE:
            driver = webdriver.Chrome(
                service=service,
                options=options,
                seleniumwire_options={
                    "verify_ssl": False,
                    "suppress_connection_errors": True,
                }
            )
        else:
            driver = webdriver.Chrome(service=service, options=options)

    except Exception as e:
        log.error(f"❌ Driver başlatma hatası: {e}")
        raise

    # Gereksiz kaynakları engelle
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {
            "urls": [
                "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg",
                "*.woff", "*.woff2", "*.ttf", "*.eot",
                "*google-analytics*", "*googletagmanager*",
                "*facebook.net*", "*doubleclick.net*",
            ]
        })
    except Exception:
        pass

    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    driver.set_page_load_timeout(15)
    log.info("✅ Driver hazır")
    return driver


# ═══════════════════════════════════════════════════════
#  POPUP KAPAT  (JS ile anlık - bekleme yok)
# ═══════════════════════════════════════════════════════
def close_popups(driver):
    try:
        count = driver.execute_script("""
            const sels = [
                '.close', '.popup-close', '#close',
                '[class*="close"]', '.modal-close',
                '.overlay-close', '[aria-label="Close"]',
                '[aria-label="Kapat"]', '.btn-close',
                'button.close', '.ad-close', '#ad-close'
            ];
            let clicked = 0;
            for (const sel of sels) {
                document.querySelectorAll(sel).forEach(el => {
                    try {
                        const st = window.getComputedStyle(el);
                        if (st.display !== 'none' && st.visibility !== 'hidden') {
                            el.click();
                            clicked++;
                        }
                    } catch(e) {}
                });
            }
            return clicked;
        """)
        if count:
            log.info(f"  ❎ Popup kapatıldı: {count} adet")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
#  PLAY BUTONU  (JS ile anlık - bekleme yok)
# ═══════════════════════════════════════════════════════
def click_play(driver):
    try:
        clicked = driver.execute_script("""
            const sels = [
                '.play-button', '.btn-play', '#play-button',
                '.jw-icon-playback', '.vjs-play-button',
                '.fp-play', '.plyr__control--overlaid',
                '[class*="play-btn"]', '[class*="play_btn"]',
                '[class*="play-icon"]', '[aria-label="Play"]',
                '[aria-label="Oynat"]', '[title="Play"]',
                '[title="Oynat"]', 'button.play',
                '.overlay-play', '.player-overlay',
                '.video-overlay', '.start-player'
            ];

            for (const sel of sels) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    try {
                        const r = el.getBoundingClientRect();
                        if (r.width > 0 && r.height > 0) {
                            el.click();
                            return sel;
                        }
                    } catch(e) {}
                }
            }

            document.querySelectorAll('video').forEach(v => {
                try { v.muted = true; v.play().catch(() => {}); } catch(e) {}
            });

            return null;
        """)
        if clicked:
            log.info(f"  ▶️  Tıklandı: {clicked}")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
#  PERFORMANCE LOG → M3U8
# ═══════════════════════════════════════════════════════
def get_m3u8_from_performance_logs(driver):
    if WIRE:
        return None
    try:
        logs = driver.get_log("performance")
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                params = msg.get("params", {})
                candidates = [
                    params.get("request", {}).get("url"),
                    params.get("response", {}).get("url"),
                    params.get("documentURL"),
                ]
                for url in candidates:
                    if is_m3u8(url):
                        log.info(f"  🎯 [PerfLog] {url}")
                        return url
            except Exception:
                pass
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════
#  JS → M3U8
# ═══════════════════════════════════════════════════════
def find_in_js(driver):
    try:
        result = driver.execute_script("""
            var found = null;

            document.querySelectorAll('video, source').forEach(function(el) {
                if (!found && el.src && el.src.toLowerCase().indexOf('.m3u8') !== -1)
                    found = el.src;
                if (!found && el.currentSrc && el.currentSrc.toLowerCase().indexOf('.m3u8') !== -1)
                    found = el.currentSrc;
            });
            if (found) return found;

            try {
                var jw = jwplayer();
                var item = jw.getPlaylistItem();
                if (item && item.file && item.file.toLowerCase().indexOf('.m3u8') !== -1)
                    return item.file;
                var srcs = jw.getConfig().playlist[0].sources;
                for (var i = 0; i < srcs.length; i++) {
                    if (srcs[i].file && srcs[i].file.toLowerCase().indexOf('.m3u8') !== -1)
                        return srcs[i].file;
                }
            } catch(e) {}

            try {
                var vjs = videojs.getPlayers();
                for (var k in vjs) {
                    var s = vjs[k].currentSrc();
                    if (s && s.toLowerCase().indexOf('.m3u8') !== -1)
                        return s;
                }
            } catch(e) {}

            try {
                if (window.hls && window.hls.url && window.hls.url.indexOf('.m3u8') !== -1)
                    return window.hls.url;
            } catch(e) {}

            try {
                var keys = ['streamUrl','stream_url','hlsUrl','hls_url',
                            'videoUrl','video_url','src','source',
                            'file','playerSrc','liveSrc','liveUrl'];
                for (var i = 0; i < keys.length; i++) {
                    if (window[keys[i]] && typeof window[keys[i]] === 'string'
                        && window[keys[i]].indexOf('.m3u8') !== -1)
                        return window[keys[i]];
                }
            } catch(e) {}

            var m = document.documentElement.innerHTML.match(
                /https?:\\/\\/[^\\s'"<>]+\\.m3u8(?:\\?[^\\s'"<>]*)?/i
            );
            return m ? m[0] : null;
        """)
        if result and is_m3u8(result):
            log.info(f"  🎯 [JS] {result}")
            return result
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════
#  HTML → M3U8
# ═══════════════════════════════════════════════════════
def find_in_source(html):
    match = re.search(
        r'https?://[^\s\'"<>]+\.m3u8(?:\?[^\s\'"<>]*)?',
        html,
        re.IGNORECASE
    )
    if match:
        url = match.group(0)
        if is_m3u8(url):
            log.info(f"  🎯 [HTML] {url}")
            return url
    return None


# ═══════════════════════════════════════════════════════
#  IFRAME → M3U8
# ═══════════════════════════════════════════════════════
def handle_iframes(driver):
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        log.info(f"  🖼️  {len(iframes)} iframe bulundu")

        for idx, iframe in enumerate(iframes):
            try:
                src = iframe.get_attribute("src") or ""
                log.info(f"  🖼️  iframe[{idx}]: {src[:100]}")

                driver.switch_to.frame(iframe)
                click_play(driver)

                result = find_in_js(driver)
                if result:
                    driver.switch_to.default_content()
                    return result

                result = find_in_source(driver.page_source)
                if result:
                    driver.switch_to.default_content()
                    return result

                driver.switch_to.default_content()

            except Exception as e:
                log.debug(f"  iframe[{idx}] hata: {e}")
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
    except Exception as e:
        log.debug(f"  iframe handler: {e}")

    return None


# ═══════════════════════════════════════════════════════
#  TEK SAYFA TARA
# ═══════════════════════════════════════════════════════
def scrape_page(driver, page):
    slug = page["slug"]
    name = page["name"]
    url  = f"{BASE_URL}/{slug}"

    log.info(f"\n{'─'*55}")
    log.info(f"🔍 {name}")
    log.info(f"   URL : {url}")
    log.info(f"{'─'*55}")

    # Eski istekleri temizle
    if WIRE:
        try:
            del driver.requests
        except Exception:
            pass
    else:
        try:
            driver.get_log("performance")
        except Exception:
            pass

    # Sayfayı yükle
    try:
        driver.get(url)
        WebDriverWait(driver, BODY_WAIT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception as e:
        log.warning(f"  ⚠️ Sayfa yükleme: {e}")

    time.sleep(0.5)
    close_popups(driver)
    click_play(driver)

    m3u8_url = None

    # 1) Hemen JS kontrol
    m3u8_url = find_in_js(driver)

    # 2) Hemen HTML kontrol
    if not m3u8_url:
        m3u8_url = find_in_source(driver.page_source)

    # 3) Network / Performance log izle
    if not m3u8_url:
        log.info(f"  📡 İzleniyor ({STREAM_WAIT}s)...")
        deadline = time.time() + STREAM_WAIT

        while time.time() < deadline and not m3u8_url:
            if WIRE:
                try:
                    for r in driver.requests[-30:]:
                        if is_m3u8(r.url):
                            m3u8_url = r.url
                            log.info(f"  🎯 [Network] {m3u8_url}")
                            break
                except Exception:
                    pass
            else:
                m3u8_url = get_m3u8_from_performance_logs(driver)

            if not m3u8_url:
                time.sleep(POLL_INTERVAL)

    # 4) iframe
    if not m3u8_url:
        log.info("  🖼️  iframe içinde aranıyor...")
        m3u8_url = handle_iframes(driver)

    # 5) Son kez HTML
    if not m3u8_url:
        m3u8_url = find_in_source(driver.page_source)

    if m3u8_url:
        log.info(f"  ✅ BULUNDU → {m3u8_url}")
    else:
        log.warning(f"  ❌ {name}: M3U8 bulunamadı")

    return m3u8_url


# ═══════════════════════════════════════════════════════
#  M3U OLUŞTUR
# ═══════════════════════════════════════════════════════
def create_m3u(channels):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "#EXTM3U\n",
        f"# Site      : mahsunsports\n",
        f"# Güncelleme: {now}\n",
        f"# Toplam    : {len(channels)} kanal\n\n",
    ]
    for ch in channels:
        extinf  = '#EXTINF:-1'
        extinf += f' tvg-name="{ch["name"]}"'
        extinf += f' group-title="{ch["group"]}"'
        extinf += f',{ch["name"]}\n'
        lines.append(extinf)
        lines.append(f'{ch["url"]}\n\n')
    return "".join(lines)


# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════
def main():
    log.info("=" * 55)
    log.info("   M3U8 Scraper → MAHSUNSPORTS")
    log.info(f"   Base URL : {BASE_URL}")
    log.info(f"   Toplam   : {len(PAGES)} sayfa")
    log.info(f"   Wire     : {WIRE}")
    log.info("=" * 55)

    start    = time.time()
    driver   = None
    channels = []

    try:
        driver = get_driver()

        for i, page in enumerate(PAGES, 1):
            log.info(f"\n[{i}/{len(PAGES)}] işleniyor...")
            m3u8_url = scrape_page(driver, page)

            if m3u8_url and is_m3u8(m3u8_url):
                channels.append({
                    "name" : page["name"],
                    "url"  : m3u8_url,
                    "group": page["group"],
                })

            time.sleep(0.5)

    except Exception as e:
        log.error(f"❌ Kritik hata: {e}", exc_info=True)

    finally:
        if driver:
            try:
                driver.quit()
                log.info("🔒 Driver kapatıldı")
            except Exception:
                pass

    elapsed = round(time.time() - start, 1)

    log.info(f"\n{'='*55}")
    log.info(f"🏁 Tamamlandı!")
    log.info(f"📺 Bulunan : {len(channels)} / {len(PAGES)}")
    log.info(f"⏱️  Süre    : {elapsed}s")
    log.info(f"{'='*55}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(create_m3u(channels))
    log.info(f"✅ {OUTPUT_FILE} kaydedildi")

    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "site"           : "mahsunsports",
            "last_update"    : datetime.now().isoformat(),
            "base_url"       : BASE_URL,
            "total_channels" : len(channels),
            "duration_sec"   : elapsed,
            "channels"       : channels
        }, f, ensure_ascii=False, indent=2)
    log.info(f"✅ {STATS_FILE} kaydedildi")

    if not channels:
        log.warning("⚠️ Hiç M3U8 bulunamadı!")


if __name__ == "__main__":
    main()
