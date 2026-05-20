#!/usr/bin/env python3
"""
Mahsun Sports M3U8 Link Scraper - v2
- Çoklu iframe zincirini takip eder
- Reklam katmanlarını bypass eder
- Obfuscated/encoded linkleri decode eder
- Selenium fallback ile dinamik JS çalıştırır
"""

import re
import json
import os
import sys
import time
import base64
import hashlib
import logging
import subprocess
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

# Selenium opsiyonel import
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# YAPILANDIRMA
# ============================================================

STATE_FILE = "state.json"
M3U_FILE = "playlist.m3u"
CHANNELS_BACKUP_FILE = "channels_backup.json"
DEFAULT_BASE_URL = "https://mahsunsports35.xyz"
MAX_IFRAME_DEPTH = 6
SELENIUM_WAIT_SECONDS = 20
SELENIUM_AD_WAIT = 12

DEFAULT_CHANNELS = [
    {"title": "BeIN Sports 1", "id": "androstreamlivebs1"},
    {"title": "BeIN Sports 2", "id": "androstreamlivebs2"},
    {"title": "BeIN Sports 3", "id": "androstreamlivebs3"},
    {"title": "BeIN Sports 4", "id": "androstreamlivebs4"},
    {"title": "BeIN Sports 5", "id": "androstreamlivebs5"},
    {"title": "BeIN Sports Max 1", "id": "androstreamlivebsm1"},
    {"title": "BeIN Sports Max 2", "id": "androstreamlivebsm2"},
    {"title": "S Sport", "id": "androstreamlivess1"},
    {"title": "S Sport 2", "id": "androstreamlivess2"},
    {"title": "S Sport Plus", "id": "androstreamlivessplus1"},
    {"title": "Tivibu Spor", "id": "androstreamlivets"},
    {"title": "Tivibu Spor 1", "id": "androstreamlivets1"},
    {"title": "Tivibu Spor 2", "id": "androstreamlivets2"},
    {"title": "Tivibu Spor 3", "id": "androstreamlivets3"},
    {"title": "Tivibu Spor 4", "id": "androstreamlivets4"},
    {"title": "Smart Spor 1", "id": "androstreamlivesm1"},
    {"title": "Smart Spor 2", "id": "androstreamlivesm2"},
    {"title": "Euro Sport 1", "id": "androstreamlivees1"},
    {"title": "Euro Sport 2", "id": "androstreamlivees2"},
    {"title": "iDMAN Tv", "id": "androstreamliveidm"},
    {"title": "Trt 1", "id": "androstreamlivetrt1"},
    {"title": "Trt Spor", "id": "androstreamlivetrts"},
    {"title": "Trt Spor Yıldız", "id": "androstreamlivetrtsy"},
    {"title": "Atv", "id": "androstreamliveatv"},
    {"title": "A Spor", "id": "androstreamliveas"},
    {"title": "A2", "id": "androstreamlivea2"},
    {"title": "Tjk Tv", "id": "androstreamlivetjk"},
    {"title": "Ht Spor", "id": "androstreamliveht"},
    {"title": "Nba Tv", "id": "androstreamlivenba"},
    {"title": "Tv8", "id": "androstreamlivetv8"},
    {"title": "Tv8,5", "id": "androstreamlivetv85"},
    {"title": "Tabi Spor", "id": "androstreamlivetb"},
    {"title": "Tabi Spor 1", "id": "androstreamlivetb1"},
    {"title": "Tabi Spor 2", "id": "androstreamlivetb2"},
    {"title": "Tabi Spor 3", "id": "androstreamlivetb3"},
    {"title": "Tabi Spor 4", "id": "androstreamlivetb4"},
    {"title": "Tabi Spor 5", "id": "androstreamlivetb5"},
    {"title": "Tabi Spor 6", "id": "androstreamlivetb6"},
    {"title": "Tabi Spor 7", "id": "androstreamlivetb7"},
    {"title": "Tabi Spor 8", "id": "androstreamlivetb8"},
    {"title": "Fb Tv", "id": "androstreamlivefb"},
    {"title": "Cbc Sport", "id": "androstreamlivecbcs"},
    {"title": "Gs Tv", "id": "androstreamlivegs"},
    {"title": "Sports Tv", "id": "androstreamlivesptstv"},
    {"title": "Exxen Tv", "id": "androstreamliveexn"},
    {"title": "Exxen Sports 1", "id": "androstreamliveexn1"},
    {"title": "Exxen Sports 2", "id": "androstreamliveexn2"},
    {"title": "Exxen Sports 3", "id": "androstreamliveexn3"},
    {"title": "Exxen Sports 4", "id": "androstreamliveexn4"},
    {"title": "Exxen Sports 5", "id": "androstreamliveexn5"},
    {"title": "Exxen Sports 6", "id": "androstreamliveexn6"},
    {"title": "Exxen Sports 7", "id": "androstreamliveexn7"},
    {"title": "Exxen Sports 8", "id": "androstreamliveexn8"},
]


# ============================================================
# HTTP SESSION
# ============================================================

class SmartSession:
    """Akıllı HTTP session - cookie, referer zinciri yönetimi"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        })

    def get(self, url, referer=None, extra_headers=None, **kwargs):
        headers = {}
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "cross-site"
        if extra_headers:
            headers.update(extra_headers)

        kwargs.setdefault("timeout", 20)
        kwargs.setdefault("allow_redirects", True)

        return self.session.get(url, headers=headers, **kwargs)


# ============================================================
# M3U8 BULMA METODLARİ
# ============================================================

def find_all_m3u8_urls(text):
    """
    Bir metin bloğundan TÜM olası m3u8 URL'lerini çıkar.
    Çeşitli encoding/obfuscation yöntemlerini çözer.
    """
    urls = set()

    # 1) Doğrudan m3u8 linkleri
    direct = re.findall(
        r"""(https?://[^\s"'<>\\\)\]\}]+\.m3u8[^\s"'<>\\\)\]\}]*)""",
        text, re.IGNORECASE
    )
    for u in direct:
        urls.add(clean_url(u))

    # 2) Protocol-relative
    proto_rel = re.findall(
        r"""(//[^\s"'<>\\\)\]\}]+\.m3u8[^\s"'<>\\\)\]\}]*)""",
        text, re.IGNORECASE
    )
    for u in proto_rel:
        urls.add(clean_url("https:" + u))

    # 3) Escaped URL'ler (\/ ile)
    escaped_text = text.replace("\\/" , "/")
    if escaped_text != text:
        extra = re.findall(
            r"""(https?://[^\s"'<>\\\)\]\}]+\.m3u8[^\s"'<>\\\)\]\}]*)""",
            escaped_text, re.IGNORECASE
        )
        for u in extra:
            urls.add(clean_url(u))

    # 4) URL-encoded
    decoded_text = unquote(text)
    if decoded_text != text:
        extra = re.findall(
            r"""(https?://[^\s"'<>\\\)\]\}]+\.m3u8[^\s"'<>\\\)\]\}]*)""",
            decoded_text, re.IGNORECASE
        )
        for u in extra:
            urls.add(clean_url(u))

    # 5) Base64 encoded bloklar
    b64_blocks = re.findall(r'["\']([A-Za-z0-9+/]{40,}={0,2})["\']', text)
    for block in b64_blocks:
        try:
            decoded = base64.b64decode(block).decode("utf-8", errors="ignore")
            if ".m3u8" in decoded:
                inner = re.findall(
                    r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', decoded
                )
                for u in inner:
                    urls.add(clean_url(u))
        except Exception:
            pass

    # 6) atob() çağrıları
    atob_matches = re.findall(r'atob\s*\(\s*["\']([A-Za-z0-9+/=]+)["\']', text)
    for encoded in atob_matches:
        try:
            decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
            if ".m3u8" in decoded:
                urls.add(clean_url(decoded.strip()))
            else:
                inner = re.findall(
                    r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', decoded
                )
                for u in inner:
                    urls.add(clean_url(u))
        except Exception:
            pass

    # 7) decodeURIComponent çağrıları
    decode_matches = re.findall(
        r'decodeURIComponent\s*\(\s*["\']([^"\']+)["\']', text
    )
    for encoded in decode_matches:
        try:
            decoded = unquote(encoded)
            if ".m3u8" in decoded:
                urls.add(clean_url(decoded))
        except Exception:
            pass

    # 8) Hex encoded string'ler
    hex_matches = re.findall(r'["\']([\\x0-9a-fA-F]{20,})["\']', text)
    for h in hex_matches:
        try:
            decoded = bytes.fromhex(
                h.replace("\\x", "")
            ).decode("utf-8", errors="ignore")
            if ".m3u8" in decoded:
                inner = re.findall(
                    r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', decoded
                )
                for u in inner:
                    urls.add(clean_url(u))
        except Exception:
            pass

    # 9) String concatenation pattern: "https://" + "domain" + "/path.m3u8"
    concat = re.findall(
        r"""["']([^"']*)['"]\s*\+\s*["']([^"']*)['"]\s*\+\s*["']([^"']*\.m3u8[^"']*)['"]""",
        text
    )
    for parts in concat:
        combined = "".join(parts)
        if ".m3u8" in combined and ("http" in combined or "//" in combined):
            urls.add(clean_url(combined))

    # Filtreleme
    filtered = set()
    for u in urls:
        if not u:
            continue
        if any(skip in u.lower() for skip in [
            'example.com', 'test.m3u8', 'sample.m3u8',
            'demo.m3u8', 'placeholder'
        ]):
            continue
        filtered.add(u)

    return list(filtered)


def clean_url(url):
    """URL temizleme"""
    url = url.strip().rstrip("',\"};)")
    # Trailing garbage temizle
    url = re.sub(r'["\'\s\\<>]+$', '', url)
    return url


def find_js_source_urls(text):
    """
    JS içinden source/file/url olarak atanan tüm URL'leri bul.
    m3u8 olmasa bile (player config'leri genelde farklı uzantılı olabiliyor).
    """
    urls = set()

    patterns = [
        # source: "url", file: "url", src: "url"
        r'''(?:source|src|file|url|stream|video|hls|dash|mp4)\s*[:=]\s*["']([^"']+)["']''',
        # loadSource("url"), setSrc("url")
        r'''(?:loadSource|setSrc|setup|load|play|setUrl|source)\s*\(\s*["']([^"']+)["']''',
        # {src: "url"}, {file: "url"}
        r'''\{\s*(?:src|file|source|url)\s*:\s*["']([^"']+)["']''',
        # data-src="url", data-stream="url"
        r'''data-(?:src|stream|url|source|video|file)\s*=\s*["']([^"']+)["']''',
    ]

    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            if any(ext in m.lower() for ext in ['.m3u8', '.mpd', '.mp4', '.ts', '/live/', '/stream/', '/hls/']):
                if m.startswith('//'):
                    m = 'https:' + m
                urls.add(m)

    return list(urls)


def find_iframe_sources(html, page_url):
    """Sayfadaki tüm iframe kaynaklarını bul"""
    sources = []
    soup = BeautifulSoup(html, 'html.parser')

    for iframe in soup.find_all(['iframe', 'embed', 'object']):
        src = (
            iframe.get('src') or
            iframe.get('data-src') or
            iframe.get('data-lazy-src') or
            iframe.get('data-url') or
            iframe.get('data') or  # <object data="...">
            ''
        )
        if not src or src.startswith('about:') or src.startswith('javascript:'):
            continue

        src = make_absolute(src, page_url)
        if src:
            sources.append(src)

    # JS ile oluşturulan iframe'leri de bul
    # document.createElement('iframe'); iframe.src = "..."
    js_iframes = re.findall(
        r'''(?:iframe|frame)\.(?:src|setAttribute\s*\(\s*["']src["']\s*,)\s*=?\s*["']([^"']+)["']''',
        html, re.IGNORECASE
    )
    for src in js_iframes:
        src = make_absolute(src, page_url)
        if src:
            sources.append(src)

    # innerHTML ile oluşturulan iframe
    inner_iframes = re.findall(
        r'''<iframe[^>]+src\s*=\s*["\\]*["']?([^"'\s>\\]+)''',
        html, re.IGNORECASE
    )
    for src in inner_iframes:
        src = src.replace("\\/", "/").replace("\\", "")
        src = make_absolute(src, page_url)
        if src:
            sources.append(src)

    # window.location, window.open ile yönlendirme
    redirects = re.findall(
        r'''(?:window\.location(?:\.href)?\s*=|window\.open\s*\()\s*["']([^"']+)["']''',
        html, re.IGNORECASE
    )
    for src in redirects:
        src = make_absolute(src, page_url)
        if src and '.m3u8' not in src:
            sources.append(src)

    return list(dict.fromkeys(sources))  # deduplicate, preserve order


def make_absolute(url, base_url):
    """Relative URL'yi absolute yap"""
    if not url:
        return None

    url = url.strip()

    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('http'):
        return url
    if url.startswith('/'):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{url}"
    if not url.startswith('http'):
        return urljoin(base_url, url)
    return url


# ============================================================
# REQUESTS TABANLI DERİN TARAMA
# ============================================================

def deep_crawl_for_m3u8(session, start_url, base_url, depth=0, visited=None):
    """
    Recursive iframe/redirect zincirini takip ederek m3u8 bul.
    Reklam sayfalarını geçer, asıl player'a ulaşır.
    """
    if visited is None:
        visited = set()

    if depth > MAX_IFRAME_DEPTH:
        return None
    if start_url in visited:
        return None

    visited.add(start_url)
    indent = "  " * depth

    logger.info(f"{indent}[Depth {depth}] Taranıyor: {start_url[:100]}")

    try:
        resp = session.get(start_url, referer=base_url if depth == 0 else start_url)
        if resp.status_code != 200:
            logger.debug(f"{indent}HTTP {resp.status_code}")
            return None

        content = resp.text
        final_url = resp.url  # redirect sonrası gerçek URL

        # 1) Bu sayfada doğrudan m3u8 var mı?
        m3u8_urls = find_all_m3u8_urls(content)
        if m3u8_urls:
            best = pick_best_m3u8(m3u8_urls)
            logger.info(f"{indent}✓ m3u8 bulundu: {best[:80]}")
            return best

        # 2) JS source/file atamalarında URL var mı?
        js_urls = find_js_source_urls(content)
        for js_url in js_urls:
            if '.m3u8' in js_url:
                logger.info(f"{indent}✓ JS source m3u8: {js_url[:80]}")
                return js_url

        # 3) Sayfadaki script dosyalarını tara
        m3u8 = scan_external_scripts(session, content, final_url)
        if m3u8:
            logger.info(f"{indent}✓ External script m3u8: {m3u8[:80]}")
            return m3u8

        # 4) API/AJAX endpoint'leri
        m3u8 = try_api_endpoints(session, content, final_url)
        if m3u8:
            logger.info(f"{indent}✓ API m3u8: {m3u8[:80]}")
            return m3u8

        # 5) iframe'leri recursive takip et
        iframe_urls = find_iframe_sources(content, final_url)
        logger.info(f"{indent}  {len(iframe_urls)} iframe bulundu")

        for iframe_url in iframe_urls:
            # Reklam domain'lerini atla
            if is_ad_domain(iframe_url):
                logger.debug(f"{indent}  [AD] Atlanıyor: {iframe_url[:60]}")
                continue

            result = deep_crawl_for_m3u8(
                session, iframe_url, final_url, depth + 1, visited
            )
            if result:
                return result

        # 6) JS redirect'lerini takip et
        redirects = find_js_redirects(content, final_url)
        for redirect_url in redirects:
            if redirect_url not in visited and not is_ad_domain(redirect_url):
                result = deep_crawl_for_m3u8(
                    session, redirect_url, final_url, depth + 1, visited
                )
                if result:
                    return result

    except requests.exceptions.RequestException as e:
        logger.debug(f"{indent}İstek hatası: {e}")

    return None


def scan_external_scripts(session, html, page_url):
    """Sayfadaki harici script dosyalarını tara"""
    soup = BeautifulSoup(html, 'html.parser')

    skip_domains = [
        'google', 'facebook', 'twitter', 'jquery', 'bootstrap',
        'cloudflare', 'jsdelivr', 'unpkg', 'cdnjs', 'analytics',
        'doubleclick', 'adservice', 'googlesyndication',
        'googletagmanager', 'fontawesome', 'gstatic'
    ]

    for script in soup.find_all('script', src=True):
        src = make_absolute(script['src'], page_url)
        if not src:
            continue

        # CDN/reklam scriptlerini atla
        src_lower = src.lower()
        if any(skip in src_lower for skip in skip_domains):
            continue

        try:
            resp = session.get(src, referer=page_url)
            if resp.status_code == 200:
                m3u8_urls = find_all_m3u8_urls(resp.text)
                if m3u8_urls:
                    return pick_best_m3u8(m3u8_urls)

                js_urls = find_js_source_urls(resp.text)
                for u in js_urls:
                    if '.m3u8' in u:
                        return u
        except Exception:
            continue

    # Inline script'lerdeki harici URL'leri de kontrol et
    for script in soup.find_all('script', src=False):
        if script.string:
            # fetch/XMLHttpRequest URL'leri
            fetch_urls = re.findall(
                r'''(?:fetch|XMLHttpRequest|\.open|\.get|\.post|axios)\s*\(\s*["']([^"']+)["']''',
                script.string, re.IGNORECASE
            )
            for fu in fetch_urls:
                fu = make_absolute(fu, page_url)
                if fu and not is_ad_domain(fu):
                    try:
                        resp = session.get(fu, referer=page_url)
                        if resp.status_code == 200:
                            m3u8_urls = find_all_m3u8_urls(resp.text)
                            if m3u8_urls:
                                return pick_best_m3u8(m3u8_urls)
                    except Exception:
                        continue

    return None


def try_api_endpoints(session, html, page_url):
    """Sayfa içeriğinden API endpoint'lerini tespit et ve dene"""
    parsed = urlparse(page_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    # URL'den id parametresini çıkar
    params = parse_qs(parsed.query)
    channel_id = params.get('id', [None])[0]

    # Sayfadaki JSON API çağrılarını bul
    api_patterns = re.findall(
        r'''["'](/(?:api|stream|live|player|channel|get|load|video)[^"']*?)["']''',
        html, re.IGNORECASE
    )

    endpoints = []
    for ep in api_patterns:
        full_url = base + ep
        if channel_id and '{' not in ep:
            endpoints.append(full_url)

    # Standart endpoint'leri de dene
    if channel_id:
        standard_eps = [
            f"{base}/api/stream/{channel_id}",
            f"{base}/api/channel/{channel_id}",
            f"{base}/api/live/{channel_id}",
            f"{base}/get_stream.php?id={channel_id}",
            f"{base}/stream.php?id={channel_id}",
            f"{base}/player/load?id={channel_id}",
            f"{base}/ajax/stream?id={channel_id}",
            f"{base}/embed/{channel_id}",
            f"{base}/player.html?id={channel_id}",
            f"{base}/play/{channel_id}",
            f"{base}/watch/{channel_id}",
            f"{base}/channel/{channel_id}",
            f"{base}/live/{channel_id}",
            f"{base}/hls/{channel_id}/index.m3u8",
            f"{base}/live/{channel_id}/index.m3u8",
            f"{base}/stream/{channel_id}/index.m3u8",
            f"{base}/{channel_id}.m3u8",
            f"{base}/streams/{channel_id}.m3u8",
        ]
        endpoints.extend(standard_eps)

    for ep_url in endpoints:
        try:
            resp = session.get(ep_url, referer=page_url)
            if resp.status_code != 200:
                continue

            ct = resp.headers.get('Content-Type', '').lower()

            # Doğrudan m3u8 içeriği
            if 'mpegurl' in ct or 'application/vnd.apple' in ct:
                return ep_url

            if resp.text.strip().startswith('#EXTM3U'):
                return ep_url

            # JSON response
            if 'json' in ct:
                try:
                    data = resp.json()
                    m3u8 = find_m3u8_in_json(data)
                    if m3u8:
                        return m3u8
                except Exception:
                    pass

            # HTML/text response
            m3u8_urls = find_all_m3u8_urls(resp.text)
            if m3u8_urls:
                return pick_best_m3u8(m3u8_urls)

        except Exception:
            continue

    return None


def find_js_redirects(html, page_url):
    """JavaScript yönlendirmelerini bul"""
    redirects = []

    patterns = [
        r'''window\.location\s*=\s*["']([^"']+)["']''',
        r'''window\.location\.href\s*=\s*["']([^"']+)["']''',
        r'''window\.location\.replace\s*\(\s*["']([^"']+)["']''',
        r'''document\.location\s*=\s*["']([^"']+)["']''',
        r'''window\.open\s*\(\s*["']([^"']+)["']''',
        r'''\.navigate\s*\(\s*["']([^"']+)["']''',
        r'''location\.assign\s*\(\s*["']([^"']+)["']''',
        r'''<meta[^>]+http-equiv\s*=\s*["']refresh["'][^>]+content\s*=\s*["']\d+;\s*url=([^"'\s]+)''',
    ]

    for pat in patterns:
        matches = re.findall(pat, html, re.IGNORECASE)
        for m in matches:
            url = make_absolute(m, page_url)
            if url:
                redirects.append(url)

    return redirects


def find_m3u8_in_json(data, depth=0):
    """JSON yapısı içinde recursive m3u8 arama"""
    if depth > 8:
        return None

    if isinstance(data, str):
        if '.m3u8' in data:
            if data.startswith('//'):
                data = 'https:' + data
            return data
        return None

    if isinstance(data, dict):
        priority = ['url', 'src', 'source', 'stream', 'file', 'hls',
                     'stream_url', 'video_url', 'link', 'playUrl',
                     'streamUrl', 'hlsUrl', 'm3u8', 'manifest']
        for key in priority:
            if key in data:
                result = find_m3u8_in_json(data[key], depth + 1)
                if result:
                    return result
        for key, val in data.items():
            if key not in priority:
                result = find_m3u8_in_json(val, depth + 1)
                if result:
                    return result

    if isinstance(data, list):
        for item in data:
            result = find_m3u8_in_json(item, depth + 1)
            if result:
                return result

    return None


def pick_best_m3u8(urls):
    """Birden fazla m3u8 URL'si varsa en iyisini seç"""
    if not urls:
        return None
    if len(urls) == 1:
        return urls[0]

    # Öncelik sıralaması
    scored = []
    for url in urls:
        score = 0
        url_lower = url.lower()

        # Token/auth içeren = canlı yayın linki olma olasılığı yüksek
        if 'token' in url_lower or 'auth' in url_lower:
            score += 10
        if 'live' in url_lower:
            score += 5
        if 'playlist' in url_lower:
            score += 3
        if 'master' in url_lower:
            score += 2
        if 'index' in url_lower:
            score += 1
        # Uzun URL'ler genelde gerçek stream
        score += min(len(url) // 20, 5)
        # Reklam domain'leri penalty
        if is_ad_domain(url):
            score -= 20

        scored.append((score, url))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


AD_DOMAINS = [
    'doubleclick', 'googlesyndication', 'googleadservices',
    'adservice', 'facebook.com/tr', 'analytics',
    'adsense', 'adnxs', 'pubmatic', 'rubiconproject',
    'criteo', 'taboola', 'outbrain', 'popads',
    'popcash', 'propellerads', 'adsterra', 'exoclick',
    'juicyads', 'trafficjunky', 'clickadu', 'hilltopads',
    'ad-maven', 'admaven', 'bidvertiser', 'revcontent',
    'mgid', 'content.ad', 'adversal', 'yllix',
    'ad.plus', 'adcash', 'clickaine', 'pushground',
    'richpush', 'evadav', 'galaksion', 'monetag',
    'profitablegatecpm', 'disqus', 'sharethis',
]


def is_ad_domain(url):
    """URL'nin reklam domain'ine ait olup olmadığını kontrol et"""
    url_lower = url.lower()
    return any(ad in url_lower for ad in AD_DOMAINS)


# ============================================================
# SELENIUM TABANLI TARAMA (Fallback)
# ============================================================

def extract_m3u8_selenium(event_url, base_url):
    """
    Selenium ile sayfayı aç, reklamları bekle/geç,
    network request'lerden m3u8 linkini yakala.
    """
    if not SELENIUM_AVAILABLE:
        logger.warning("Selenium yüklü değil, atlanıyor.")
        return None

    logger.info(f"  [Selenium] Başlatılıyor: {event_url[:80]}")

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-notifications")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    # Performance logging aktif (network request yakalama)
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)

        # Sayfayı aç
        driver.get(event_url)

        # Reklam bekleme süresi
        logger.info(f"  [Selenium] Reklam bekleniyor ({SELENIUM_AD_WAIT}s)...")
        time.sleep(SELENIUM_AD_WAIT)

        # Popup/overlay kapatma dene
        close_popups(driver)

        # Biraz daha bekle (video yüklensin)
        time.sleep(5)

        m3u8_url = None

        # Yöntem 1: Performance log'lardan network request'leri tara
        m3u8_url = find_m3u8_from_network_logs(driver)
        if m3u8_url:
            logger.info(f"  [Selenium/Network] ✓ {m3u8_url[:80]}")
            return m3u8_url

        # Yöntem 2: Tüm iframe'lere gir ve page source'u tara
        m3u8_url = find_m3u8_from_all_frames(driver)
        if m3u8_url:
            logger.info(f"  [Selenium/Frame] ✓ {m3u8_url[:80]}")
            return m3u8_url

        # Yöntem 3: JS ile doğrudan sor
        m3u8_url = find_m3u8_via_js(driver)
        if m3u8_url:
            logger.info(f"  [Selenium/JS] ✓ {m3u8_url[:80]}")
            return m3u8_url

        logger.warning(f"  [Selenium] m3u8 bulunamadı")
        return None

    except WebDriverException as e:
        logger.error(f"  [Selenium] WebDriver hatası: {e}")
        return None
    except Exception as e:
        logger.error(f"  [Selenium] Hata: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def close_popups(driver):
    """Selenium ile popup/overlay kapatma"""
    # Yaygın kapatma butonları
    close_selectors = [
        '[class*="close"]', '[class*="dismiss"]', '[class*="skip"]',
        '[id*="close"]', '[id*="dismiss"]', '[id*="skip"]',
        'button[aria-label="Close"]', '.modal .close',
        '.overlay-close', '.ad-close', '.popup-close',
        '[class*="btn-close"]', '.skip-ad', '#skip-button',
        'a[class*="close"]', 'div[class*="close"]',
    ]

    for selector in close_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    el.click()
                    time.sleep(0.5)
        except Exception:
            continue

    # Overlay div'leri kaldır (JS ile)
    try:
        driver.execute_script("""
            // Overlay ve reklam katmanlarını kaldır
            var overlays = document.querySelectorAll(
                '[class*="overlay"], [class*="popup"], [class*="modal"], ' +
                '[class*="ad-"], [id*="overlay"], [id*="popup"], ' +
                '[class*="interstitial"], [class*="preroll"]'
            );
            overlays.forEach(function(el) {
                if (el.style) {
                    el.style.display = 'none';
                    el.remove();
                }
            });

            // Body overflow fix
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
        """)
    except Exception:
        pass


def find_m3u8_from_network_logs(driver):
    """Chrome DevTools performance log'larından m3u8 request'lerini bul"""
    try:
        logs = driver.get_log("performance")
        m3u8_urls = []

        for entry in logs:
            try:
                log_data = json.loads(entry["message"])
                message = log_data.get("message", {})
                method = message.get("method", "")

                # Network request/response olayları
                if method in [
                    "Network.requestWillBeSent",
                    "Network.responseReceived",
                    "Network.responseReceivedExtraInfo",
                ]:
                    params = message.get("params", {})

                    # Request URL
                    url = ""
                    if "request" in params:
                        url = params["request"].get("url", "")
                    elif "response" in params:
                        url = params["response"].get("url", "")

                    if ".m3u8" in url:
                        m3u8_urls.append(url)

                    # Redirect URL
                    redirect_url = params.get("redirectUrl", "")
                    if ".m3u8" in redirect_url:
                        m3u8_urls.append(redirect_url)

            except (json.JSONDecodeError, KeyError):
                continue

        if m3u8_urls:
            return pick_best_m3u8(list(set(m3u8_urls)))

    except Exception as e:
        logger.debug(f"Network log okuma hatası: {e}")

    return None


def find_m3u8_from_all_frames(driver):
    """Tüm frame'lere geçip page source'da m3u8 ara"""
    all_m3u8 = []

    # Ana frame
    try:
        driver.switch_to.default_content()
        source = driver.page_source
        urls = find_all_m3u8_urls(source)
        all_m3u8.extend(urls)
    except Exception:
        pass

    # Nested frame'leri recursive tara
    def scan_frames(depth=0):
        if depth > MAX_IFRAME_DEPTH:
            return
        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for i in range(len(iframes)):
                try:
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    if i >= len(iframes):
                        break
                    driver.switch_to.frame(iframes[i])

                    source = driver.page_source
                    urls = find_all_m3u8_urls(source)
                    all_m3u8.extend(urls)

                    js_urls = find_js_source_urls(source)
                    for u in js_urls:
                        if '.m3u8' in u:
                            all_m3u8.append(u)

                    # Daha derin frame'ler
                    scan_frames(depth + 1)

                    driver.switch_to.parent_frame()
                except Exception:
                    try:
                        driver.switch_to.parent_frame()
                    except Exception:
                        driver.switch_to.default_content()
                    continue
        except Exception:
            pass

    scan_frames()
    driver.switch_to.default_content()

    if all_m3u8:
        return pick_best_m3u8(list(set(all_m3u8)))
    return None


def find_m3u8_via_js(driver):
    """JavaScript ile player objelerinden m3u8 linkini çıkar"""
    js_commands = [
        # HLS.js
        """
        if (typeof Hls !== 'undefined') {
            var players = document.querySelectorAll('video');
            for (var p of players) {
                if (p.hlsPlayer && p.hlsPlayer.url) return p.hlsPlayer.url;
            }
            // Global hls instance
            if (window.hls && window.hls.url) return window.hls.url;
        }
        return null;
        """,
        # Clappr
        """
        if (window.player && window.player.core) {
            var src = window.player.core.activeContainer &&
                      window.player.core.activeContainer.playback &&
                      window.player.core.activeContainer.playback.options &&
                      window.player.core.activeContainer.playback.options.src;
            if (src) return src;
        }
        return null;
        """,
        # Video.js
        """
        if (typeof videojs !== 'undefined') {
            var players = videojs.getAllPlayers();
            for (var p of players) {
                var src = p.currentSrc();
                if (src && src.includes('.m3u8')) return src;
            }
        }
        return null;
        """,
        # FlowPlayer
        """
        if (typeof flowplayer !== 'undefined') {
            var fp = flowplayer();
            if (fp && fp.video && fp.video.src) return fp.video.src;
        }
        return null;
        """,
        # JW Player
        """
        if (typeof jwplayer !== 'undefined') {
            var p = jwplayer();
            if (p) {
                var playlist = p.getPlaylist();
                if (playlist && playlist[0] && playlist[0].file) return playlist[0].file;
                var config = p.getConfig();
                if (config && config.file) return config.file;
            }
        }
        return null;
        """,
        # Video element src
        """
        var videos = document.querySelectorAll('video');
        for (var v of videos) {
            if (v.src && v.src.includes('.m3u8')) return v.src;
            var sources = v.querySelectorAll('source');
            for (var s of sources) {
                if (s.src && s.src.includes('.m3u8')) return s.src;
            }
        }
        return null;
        """,
        # Genel global değişken arama
        """
        var keys = ['streamUrl', 'stream_url', 'hlsUrl', 'hls_url',
                     'videoUrl', 'video_url', 'playerUrl', 'source',
                     'streamSrc', 'videoSrc', 'm3u8Url', 'liveUrl'];
        for (var k of keys) {
            if (window[k] && typeof window[k] === 'string' &&
                window[k].includes('.m3u8')) {
                return window[k];
            }
        }
        return null;
        """,
    ]

    for js_cmd in js_commands:
        try:
            result = driver.execute_script(js_cmd)
            if result and '.m3u8' in str(result):
                return result
        except Exception:
            continue

    # Her frame'de de dene
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for i in range(min(len(iframes), 5)):
            try:
                driver.switch_to.frame(iframes[i])
                for js_cmd in js_commands:
                    try:
                        result = driver.execute_script(js_cmd)
                        if result and '.m3u8' in str(result):
                            driver.switch_to.default_content()
                            return result
                    except Exception:
                        continue
                driver.switch_to.parent_frame()
            except Exception:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
    except Exception:
        pass

    driver.switch_to.default_content()
    return None


# ============================================================
# DOMAIN & KANAL YÖNETİMİ
# ============================================================

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "base_url": DEFAULT_BASE_URL,
        "last_update": None,
        "domain_history": [DEFAULT_BASE_URL],
        "script_hash": None,
    }


def save_state(state):
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def resolve_base_url(state):
    """Aktif domain'i bul"""
    current = state.get("base_url", DEFAULT_BASE_URL)
    session = SmartSession()

    # Mevcut URL'yi kontrol et
    try:
        resp = session.get(current)
        final = resp.url.rstrip('/')
        original = current.rstrip('/')

        if resp.status_code == 200:
            if final != original:
                parsed = urlparse(final)
                new_base = f"{parsed.scheme}://{parsed.netloc}"
                logger.info(f"Redirect tespit: {current} -> {new_base}")
                state["base_url"] = new_base
                if new_base not in state.get("domain_history", []):
                    state["domain_history"].append(new_base)
                return new_base
            return current
    except Exception:
        pass

    # Mevcut çalışmıyorsa yeni domain ara
    logger.warning(f"Domain erişilemez: {current}")

    parsed = urlparse(current)
    match = re.search(r'(mahsunsports)(\d+)(\..*)', parsed.hostname or '')
    if match:
        prefix, num, suffix = match.group(1), int(match.group(2)), match.group(3)
        for delta in range(1, 15):
            new_num = num + delta
            new_host = f"{prefix}{new_num}{suffix}"
            new_url = f"{parsed.scheme}://{new_host}"
            logger.info(f"Domain deneniyor: {new_url}")
            try:
                resp = session.get(new_url)
                if resp.status_code == 200:
                    final_parsed = urlparse(resp.url)
                    found = f"{final_parsed.scheme}://{final_parsed.netloc}"
                    logger.info(f"Yeni domain bulundu: {found}")
                    state["base_url"] = found
                    if found not in state.get("domain_history", []):
                        state["domain_history"].append(found)
                    return found
            except Exception:
                continue

    logger.error("Aktif domain bulunamadı!")
    return current


def fetch_script_channels(base_url, state):
    """Script dosyasından kanal listesini çek"""
    session = SmartSession()

    # Ana sayfadan script dosyalarını keşfet
    script_candidates = []
    try:
        resp = session.get(base_url)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup.find_all('script', src=True):
                src = tag['src']
                if not src.startswith('http'):
                    src = src.lstrip('./')
                script_candidates.append(src)
    except Exception:
        pass

    # Bilinen script isimleri
    known = [
        "script4.js", "script3.js", "script5.js", "script6.js",
        "script2.js", "script.js", "script1.js",
        "channels.js", "config.js", "main.js", "app.js"
    ]

    all_scripts = list(dict.fromkeys(script_candidates + known))

    for script_name in all_scripts:
        if script_name.startswith('http'):
            script_url = script_name
        else:
            script_url = f"{base_url}/{script_name}"

        try:
            resp = session.get(script_url, referer=base_url)
            if resp.status_code != 200:
                continue

            channels = parse_channels_from_script(resp.text)
            if channels:
                content_hash = hashlib.md5(resp.text.encode()).hexdigest()
                old_hash = state.get("script_hash")
                if old_hash and old_hash != content_hash:
                    logger.info(f"Kanal listesi değişti! ({script_name})")
                state["script_hash"] = content_hash

                with open(CHANNELS_BACKUP_FILE, 'w', encoding='utf-8') as f:
                    json.dump(channels, f, indent=2, ensure_ascii=False)

                logger.info(f"{len(channels)} kanal bulundu ({script_name})")
                return channels
        except Exception:
            continue

    # Yedekten yükle
    if os.path.exists(CHANNELS_BACKUP_FILE):
        try:
            with open(CHANNELS_BACKUP_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    return DEFAULT_CHANNELS


def parse_channels_from_script(content):
    """JavaScript'ten kanal listesini parse et"""
    channels = []

    pattern = re.findall(
        r'\{\s*title\s*:\s*["\']([^"\']+)["\']\s*,\s*url\s*:\s*["\']([^"\']+)["\']\s*\}',
        content, re.DOTALL
    )
    if not pattern:
        pattern = re.findall(
            r'\{\s*url\s*:\s*["\']([^"\']+)["\']\s*,\s*title\s*:\s*["\']([^"\']+)["\']\s*\}',
            content, re.DOTALL
        )
        pattern = [(title, url) for url, title in pattern]

    for title, url in pattern:
        match = re.search(r'id=([^&"\']+)', url)
        if match:
            channels.append({"title": title, "id": match.group(1)})
        else:
            channels.append({"title": title, "id": url.strip('/')})

    return channels


# ============================================================
# M3U OLUŞTURMA
# ============================================================

def generate_m3u(entries):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    group_map = {
        'bein': 'BeIN Sports', 'ssport': 'S Sport', 's sport': 'S Sport',
        'tivibu': 'Tivibu Spor', 'smart': 'Smart Spor',
        'euro': 'Euro Sport', 'trt': 'TRT', 'exxen': 'Exxen',
        'tabi': 'Tabi Spor', 'nba': 'NBA', 'cbc': 'CBC',
    }

    lines = [
        '#EXTM3U',
        f'#PLAYLIST:Mahsun Sports',
        f'# Güncelleme: {now}',
        f'# Kanal sayısı: {len(entries)}',
        '',
    ]

    for entry in entries:
        title = entry['title']
        url = entry['url']

        group = 'Diğer'
        tl = title.lower().replace(' ', '')
        for key, grp in group_map.items():
            if key in tl:
                group = grp
                break

        lines.append(
            f'#EXTINF:-1 tvg-name="{title}" '
            f'group-title="{group}",{title}'
        )
        lines.append(url)
        lines.append('')

    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info(f"✓ M3U oluşturuldu: {len(entries)} kanal -> {M3U_FILE}")


# ============================================================
# ANA FONKSİYON
# ============================================================

def run():
    logger.info("=" * 65)
    logger.info("  Mahsun Sports M3U Playlist Generator v2")
    logger.info("  iframe zinciri + reklam bypass + Selenium fallback")
    logger.info("=" * 65)

    state = load_state()

    # 1) Domain kontrolü
    logger.info("\n[1/4] Domain kontrolü...")
    base_url = resolve_base_url(state)
    logger.info(f"Aktif URL: {base_url}")

    # 2) Kanal listesi
    logger.info("\n[2/4] Kanal listesi alınıyor...")
    channels = fetch_script_channels(base_url, state)
    logger.info(f"Toplam kanal: {len(channels)}")

    # 3) Her kanaldan m3u8 çıkar
    logger.info("\n[3/4] m3u8 linkleri çıkarılıyor...")
    session = SmartSession()
    entries = []
    success = 0
    fail = 0

    for i, ch in enumerate(channels, 1):
        title = ch.get('title', '?')
        channel_id = ch.get('id', '')

        logger.info(f"\n{'─'*50}")
        logger.info(f"[{i}/{len(channels)}] {title} ({channel_id})")

        event_url = f"{base_url}/event.html?id={channel_id}"
        m3u8 = None

        # Yöntem A: Requests tabanlı derin tarama
        m3u8 = deep_crawl_for_m3u8(session, event_url, base_url)

        # Yöntem B: Selenium fallback
        if not m3u8 and SELENIUM_AVAILABLE:
            m3u8 = extract_m3u8_selenium(event_url, base_url)

        if m3u8:
            entries.append({"title": title, "url": m3u8})
            success += 1
            logger.info(f"✓ {title}: {m3u8[:80]}")
        else:
            fail += 1
            logger.warning(f"✗ {title}: m3u8 bulunamadı")

        # Rate limit
        time.sleep(2)

    # 4) M3U oluştur
    logger.info(f"\n{'─'*50}")
    logger.info(f"\n[4/4] M3U dosyası oluşturuluyor...")
    logger.info(f"Sonuç: {success} başarılı / {fail} başarısız")

    if entries:
        generate_m3u(entries)
    else:
        logger.error("Hiçbir m3u8 bulunamadı! Eski playlist korunuyor.")

    save_state(state)
    logger.info("\n✓ İşlem tamamlandı.")


if __name__ == "__main__":
    run()
