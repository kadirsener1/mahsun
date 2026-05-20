#!/usr/bin/env python3
"""
Mahsun Sports M3U8 Link Scraper & M3U Playlist Generator
- Kanal listesinden m3u8 linklerini çıkarır
- M3U playlist dosyası oluşturur
- Site domain değişikliklerini takip eder
- Her 31 dakikada bir güncellenir
"""

import re
import json
import os
import time
import logging
import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# YAPILANDIRMA
# ============================================================

STATE_FILE = "state.json"
M3U_FILE = "playlist.m3u"
CHANNELS_BACKUP_FILE = "channels_backup.json"

DEFAULT_BASE_URL = "https://mahsunsports35.xyz"

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
# DURUM YÖNETİMİ
# ============================================================

def load_state():
    """Önceki çalışma durumunu yükle"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"State dosyası okunamadı: {e}")
    return {
        "base_url": DEFAULT_BASE_URL,
        "last_update": None,
        "domain_history": [DEFAULT_BASE_URL],
        "script_hash": None,
        "channels_hash": None
    }


def save_state(state):
    """Çalışma durumunu kaydet"""
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ============================================================
# DOMAIN DEĞİŞİKLİĞİ TESPİTİ
# ============================================================

def check_domain_redirect(base_url):
    """
    Site yönlendirme kontrolü - domain değişimini tespit et.
    mahsunsports35 -> mahsunsports36 gibi değişimleri yakalar.
    """
    headers = get_headers(base_url)
    
    try:
        resp = requests.get(
            base_url,
            headers=headers,
            timeout=15,
            allow_redirects=True
        )
        
        final_url = resp.url.rstrip('/')
        original = base_url.rstrip('/')
        
        if final_url != original:
            logger.info(f"Domain yönlendirmesi tespit edildi: {original} -> {final_url}")
            parsed = urlparse(final_url)
            new_base = f"{parsed.scheme}://{parsed.netloc}"
            return new_base
        
        return base_url
        
    except requests.exceptions.RequestException as e:
        logger.warning(f"Domain kontrol hatası ({base_url}): {e}")
        return None


def discover_new_domain(current_base):
    """
    Mevcut domain çalışmıyorsa, olası yeni domainleri dene.
    mahsunsports35 -> 36, 37, ... şeklinde artırarak dener.
    """
    parsed = urlparse(current_base)
    hostname = parsed.hostname  # örn: mahsunsports35.xyz
    
    # Numarayı bul
    match = re.search(r'(mahsunsports)(\d+)(\..*)', hostname)
    if not match:
        logger.warning("Domain pattern tanınamadı, numara artırma yapılamıyor.")
        return None
    
    prefix = match.group(1)
    current_num = int(match.group(2))
    suffix = match.group(3)
    
    # Mevcut numaradan 10 ileriye kadar dene
    for delta in range(1, 11):
        new_num = current_num + delta
        new_host = f"{prefix}{new_num}{suffix}"
        new_url = f"{parsed.scheme}://{new_host}"
        
        logger.info(f"Yeni domain deneniyor: {new_url}")
        
        try:
            resp = requests.get(
                new_url,
                headers=get_headers(new_url),
                timeout=10,
                allow_redirects=True
            )
            if resp.status_code == 200:
                final_url = resp.url.rstrip('/')
                parsed_final = urlparse(final_url)
                found_base = f"{parsed_final.scheme}://{parsed_final.netloc}"
                logger.info(f"Yeni aktif domain bulundu: {found_base}")
                return found_base
        except requests.exceptions.RequestException:
            continue
    
    logger.error("Yeni domain bulunamadı!")
    return None


def resolve_base_url(state):
    """
    Aktif base URL'yi belirle.
    1) Mevcut URL'ye bağlanmayı dene
    2) Redirect varsa takip et
    3) Çalışmıyorsa yeni domain ara
    """
    current = state.get("base_url", DEFAULT_BASE_URL)
    
    # Önce mevcut URL'yi kontrol et
    result = check_domain_redirect(current)
    
    if result and result != current:
        # Redirect tespit edildi
        state["base_url"] = result
        if result not in state.get("domain_history", []):
            state["domain_history"].append(result)
        return result
    
    if result:
        return result
    
    # Mevcut URL çalışmıyor, yeni domain ara
    logger.warning(f"Mevcut domain çalışmıyor: {current}")
    new_domain = discover_new_domain(current)
    
    if new_domain:
        state["base_url"] = new_domain
        if new_domain not in state.get("domain_history", []):
            state["domain_history"].append(new_domain)
        return new_domain
    
    # Hiçbiri çalışmıyorsa mevcut URL'yi döndür (playlist güncellenmez)
    logger.error("Hiçbir aktif domain bulunamadı!")
    return current


# ============================================================
# KANAL LİSTESİ DİNAMİK GÜNCELLEMESİ
# ============================================================

def get_headers(base_url):
    """İstek başlıklarını oluştur"""
    parsed = urlparse(base_url)
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36",
        "Referer": base_url + "/",
        "Origin": f"{parsed.scheme}://{parsed.netloc}",
        "Accept": "*/*",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }


def fetch_script_channels(base_url, state):
    """
    Site üzerindeki script dosyasından kanal listesini dinamik olarak çek.
    Birden fazla script dosyası adını dener.
    """
    script_names = [
        "script4.js", "script3.js", "script5.js", "script6.js",
        "script2.js", "script.js", "script1.js",
        "channels.js", "config.js", "main.js", "app.js"
    ]
    
    headers = get_headers(base_url)
    
    # Önce ana sayfayı çekip script referanslarını bul
    discovered_scripts = discover_scripts_from_page(base_url, headers)
    
    # Keşfedilen scriptleri listenin başına ekle
    all_scripts = []
    for s in discovered_scripts:
        if s not in all_scripts:
            all_scripts.append(s)
    for s in script_names:
        if s not in all_scripts:
            all_scripts.append(s)
    
    for script_name in all_scripts:
        script_url = f"{base_url}/{script_name}"
        logger.info(f"Script deneniyor: {script_url}")
        
        try:
            resp = requests.get(script_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                continue
            
            content = resp.text
            
            # Script içeriğinden kanal listesini çıkar
            channels = parse_channels_from_script(content)
            
            if channels:
                # Hash kontrolü - değişim var mı?
                content_hash = hashlib.md5(content.encode()).hexdigest()
                old_hash = state.get("script_hash")
                
                if old_hash and old_hash != content_hash:
                    logger.info(f"Script değişikliği tespit edildi! ({script_name})")
                
                state["script_hash"] = content_hash
                
                # Yedekle
                with open(CHANNELS_BACKUP_FILE, 'w', encoding='utf-8') as f:
                    json.dump(channels, f, indent=2, ensure_ascii=False)
                
                logger.info(f"{len(channels)} kanal bulundu ({script_name})")
                return channels
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Script erişim hatası ({script_name}): {e}")
            continue
    
    # Script'ten kanal bulunamadıysa yedekten veya varsayılandan kullan
    logger.warning("Script'ten kanal listesi alınamadı, yedek/varsayılan kullanılıyor.")
    
    if os.path.exists(CHANNELS_BACKUP_FILE):
        try:
            with open(CHANNELS_BACKUP_FILE, 'r', encoding='utf-8') as f:
                channels = json.load(f)
            logger.info(f"Yedekten {len(channels)} kanal yüklendi.")
            return channels
        except Exception:
            pass
    
    return DEFAULT_CHANNELS


def discover_scripts_from_page(base_url, headers):
    """Ana sayfadaki script etiketlerinden dosya isimlerini keşfet"""
    scripts = []
    try:
        resp = requests.get(base_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup.find_all('script', src=True):
                src = tag['src']
                # Relative path ise dosya adını al
                if not src.startswith('http'):
                    src = src.lstrip('./')
                    scripts.append(src)
                elif base_url in src:
                    path = urlparse(src).path.lstrip('/')
                    scripts.append(path)
    except Exception as e:
        logger.debug(f"Sayfa script keşfi hatası: {e}")
    
    return scripts


def parse_channels_from_script(content):
    """
    JavaScript içeriğinden kanal listesini ayrıştır.
    Birden fazla format/pattern destekler.
    """
    channels = []
    
    # Pattern 1: const channels = [...] formatı
    # title ve url/id çiftlerini yakala
    pattern1 = re.findall(
        r'\{\s*title\s*:\s*["\']([^"\']+)["\']\s*,\s*url\s*:\s*["\']([^"\']+)["\']\s*\}',
        content,
        re.DOTALL
    )
    
    if pattern1:
        for title, url in pattern1:
            # URL'den id parametresini çıkar
            if 'id=' in url:
                match = re.search(r'id=([^&"\']+)', url)
                if match:
                    channel_id = match.group(1)
                    channels.append({"title": title, "id": channel_id})
            else:
                channels.append({"title": title, "id": url})
        return channels
    
    # Pattern 2: Farklı property sırası
    pattern2 = re.findall(
        r'\{\s*url\s*:\s*["\']([^"\']+)["\']\s*,\s*title\s*:\s*["\']([^"\']+)["\']\s*\}',
        content,
        re.DOTALL
    )
    
    if pattern2:
        for url, title in pattern2:
            if 'id=' in url:
                match = re.search(r'id=([^&"\']+)', url)
                if match:
                    channel_id = match.group(1)
                    channels.append({"title": title, "id": channel_id})
        return channels
    
    # Pattern 3: name/src formatı
    pattern3 = re.findall(
        r'\{\s*name\s*:\s*["\']([^"\']+)["\']\s*,\s*(?:src|source|stream)\s*:\s*["\']([^"\']+)["\']\s*\}',
        content,
        re.DOTALL
    )
    
    if pattern3:
        for name, src in pattern3:
            if 'id=' in src:
                match = re.search(r'id=([^&"\']+)', src)
                if match:
                    channels.append({"title": name, "id": match.group(1)})
            elif '.m3u8' in src:
                channels.append({"title": name, "id": None, "direct_url": src})
            else:
                channels.append({"title": name, "id": src})
        return channels
    
    return channels


# ============================================================
# M3U8 LİNK ÇIKARMA
# ============================================================

def extract_m3u8_from_event_page(base_url, channel_id, headers):
    """
    Bir event sayfasından m3u8 linkini çıkar.
    Birden fazla yöntem dener:
    1) Sayfa HTML içinde doğrudan m3u8 linki arama
    2) JavaScript içindeki değişkenlerden
    3) iframe src üzerinden
    4) API endpoint'leri üzerinden
    """
    event_url = f"{base_url}/event.html?id={channel_id}"
    logger.info(f"İşleniyor: {channel_id} -> {event_url}")
    
    try:
        resp = requests.get(event_url, headers=headers, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"Event sayfası erişilemedi ({resp.status_code}): {event_url}")
            return None
        
        page_content = resp.text
        
        # Yöntem 1: Doğrudan m3u8 linki ara
        m3u8_url = find_m3u8_direct(page_content)
        if m3u8_url:
            logger.info(f"  [Direkt] m3u8 bulundu: {m3u8_url[:80]}...")
            return m3u8_url
        
        # Yöntem 2: JavaScript değişkenlerinden
        m3u8_url = find_m3u8_from_js_vars(page_content)
        if m3u8_url:
            logger.info(f"  [JS Var] m3u8 bulundu: {m3u8_url[:80]}...")
            return m3u8_url
        
        # Yöntem 3: iframe src'lerini kontrol et
        m3u8_url = find_m3u8_from_iframes(page_content, base_url, headers)
        if m3u8_url:
            logger.info(f"  [iframe] m3u8 bulundu: {m3u8_url[:80]}...")
            return m3u8_url
        
        # Yöntem 4: Script dosyaları içinden
        m3u8_url = find_m3u8_from_page_scripts(page_content, base_url, headers)
        if m3u8_url:
            logger.info(f"  [Script] m3u8 bulundu: {m3u8_url[:80]}...")
            return m3u8_url
        
        # Yöntem 5: API endpoint dene
        m3u8_url = find_m3u8_from_api(base_url, channel_id, headers)
        if m3u8_url:
            logger.info(f"  [API] m3u8 bulundu: {m3u8_url[:80]}...")
            return m3u8_url
        
        # Yöntem 6: player.html veya benzer embed sayfası
        m3u8_url = find_m3u8_from_player_page(base_url, channel_id, headers)
        if m3u8_url:
            logger.info(f"  [Player] m3u8 bulundu: {m3u8_url[:80]}...")
            return m3u8_url
        
        logger.warning(f"  m3u8 bulunamadı: {channel_id}")
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"  İstek hatası ({channel_id}): {e}")
        return None


def find_m3u8_direct(content):
    """Sayfa içeriğinde doğrudan m3u8 linklerini ara"""
    # Çeşitli m3u8 URL pattern'leri
    patterns = [
        # Tam URL
        r'(https?://[^\s"\'<>\\\)]+\.m3u8[^\s"\'<>\\\)]*)',
        # Protocol-relative
        r'(//[^\s"\'<>\\\)]+\.m3u8[^\s"\'<>\\\)]*)',
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        all_matches.extend(matches)
    
    if not all_matches:
        return None
    
    # En iyi eşleşmeyi seç (genellikle en uzun ve token içeren)
    # Öncelik: playlist/live > master > diğer
    best = None
    for url in all_matches:
        if url.startswith('//'):
            url = 'https:' + url
        
        # Bazı filtreleme
        url_lower = url.lower()
        if any(skip in url_lower for skip in ['example.com', 'test.', 'sample']):
            continue
        
        if best is None:
            best = url
        elif 'token' in url.lower() or 'auth' in url.lower():
            best = url  # Token içeren URL'ler öncelikli
        elif 'live' in url.lower() or 'playlist' in url.lower():
            if 'token' not in (best or '').lower():
                best = url
    
    return best


def find_m3u8_from_js_vars(content):
    """JavaScript değişkenlerinden m3u8 linkini bul"""
    # var source = "...", var streamUrl = "...", vs.
    var_patterns = [
        r'(?:var|let|const)\s+(?:source|streamUrl|stream_url|videoUrl|video_url|'
        r'hlsUrl|hls_url|playerUrl|player_url|url|src|file|streamSrc)\s*=\s*'
        r'["\']([^"\']*\.m3u8[^"\']*)["\']',
        
        # JSON-like assignment
        r'(?:source|src|file|url|stream)\s*:\s*["\']([^"\']*\.m3u8[^"\']*)["\']',
        
        # Hls.js veya video.js source
        r'(?:loadSource|setSrc|source)\s*\(\s*["\']([^"\']*\.m3u8[^"\']*)["\']',
        
        # atob (base64 encoded)
        r'atob\s*\(\s*["\']([A-Za-z0-9+/=]+)["\']',
    ]
    
    for pattern in var_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            # Base64 kontrolü
            if 'atob' in pattern:
                try:
                    import base64
                    decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
                    if '.m3u8' in decoded:
                        url_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', decoded)
                        if url_match:
                            return url_match.group(1)
                except Exception:
                    continue
            elif '.m3u8' in match:
                if match.startswith('//'):
                    match = 'https:' + match
                elif match.startswith('/'):
                    continue  # Relative URL, base gerekli
                return match
    
    return None


def find_m3u8_from_iframes(content, base_url, headers):
    """iframe kaynaklarını kontrol ederek m3u8 bul"""
    soup = BeautifulSoup(content, 'html.parser')
    
    iframes = soup.find_all('iframe')
    
    for iframe in iframes:
        src = iframe.get('src', '') or iframe.get('data-src', '')
        if not src:
            continue
        
        # Relative URL'yi absolute yap
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            src = base_url + src
        elif not src.startswith('http'):
            src = base_url + '/' + src
        
        logger.debug(f"  iframe kontrol: {src}")
        
        try:
            iframe_headers = headers.copy()
            iframe_headers['Referer'] = base_url + '/'
            
            resp = requests.get(src, headers=iframe_headers, timeout=15)
            if resp.status_code == 200:
                # iframe içeriğinde m3u8 ara
                m3u8 = find_m3u8_direct(resp.text)
                if m3u8:
                    return m3u8
                
                m3u8 = find_m3u8_from_js_vars(resp.text)
                if m3u8:
                    return m3u8
                
                # Nested iframe kontrolü (1 seviye daha)
                nested_soup = BeautifulSoup(resp.text, 'html.parser')
                for nested_iframe in nested_soup.find_all('iframe'):
                    nested_src = nested_iframe.get('src', '')
                    if nested_src:
                        if nested_src.startswith('//'):
                            nested_src = 'https:' + nested_src
                        elif nested_src.startswith('/'):
                            parsed = urlparse(src)
                            nested_src = f"{parsed.scheme}://{parsed.netloc}{nested_src}"
                        
                        try:
                            nested_headers = headers.copy()
                            nested_headers['Referer'] = src
                            
                            nested_resp = requests.get(
                                nested_src, headers=nested_headers, timeout=15
                            )
                            if nested_resp.status_code == 200:
                                m3u8 = find_m3u8_direct(nested_resp.text)
                                if m3u8:
                                    return m3u8
                                m3u8 = find_m3u8_from_js_vars(nested_resp.text)
                                if m3u8:
                                    return m3u8
                        except Exception:
                            continue
                
        except requests.exceptions.RequestException:
            continue
    
    return None


def find_m3u8_from_page_scripts(content, base_url, headers):
    """Sayfadaki harici script dosyalarını kontrol et"""
    soup = BeautifulSoup(content, 'html.parser')
    
    for script_tag in soup.find_all('script', src=True):
        src = script_tag['src']
        
        if src.startswith('//'):
            src = 'https:' + src
        elif src.startswith('/'):
            src = base_url + src
        elif not src.startswith('http'):
            src = base_url + '/' + src
        
        # CDN script'lerini atla
        if any(skip in src.lower() for skip in [
            'jquery', 'bootstrap', 'analytics', 'gtag',
            'cloudflare', 'cdn.jsdelivr', 'unpkg'
        ]):
            continue
        
        try:
            resp = requests.get(src, headers=headers, timeout=10)
            if resp.status_code == 200:
                m3u8 = find_m3u8_direct(resp.text)
                if m3u8:
                    return m3u8
                m3u8 = find_m3u8_from_js_vars(resp.text)
                if m3u8:
                    return m3u8
        except Exception:
            continue
    
    return None


def find_m3u8_from_api(base_url, channel_id, headers):
    """Olası API endpoint'lerinden m3u8 linkini bul"""
    api_patterns = [
        f"{base_url}/api/stream/{channel_id}",
        f"{base_url}/api/channel/{channel_id}",
        f"{base_url}/api/live/{channel_id}",
        f"{base_url}/get_stream.php?id={channel_id}",
        f"{base_url}/stream.php?id={channel_id}",
        f"{base_url}/player/load.php?id={channel_id}",
        f"{base_url}/ajax/stream?id={channel_id}",
        f"{base_url}/live/{channel_id}",
        f"{base_url}/play/{channel_id}",
    ]
    
    for api_url in api_patterns:
        try:
            resp = requests.get(api_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                # JSON response
                try:
                    data = resp.json()
                    # JSON içinde m3u8 ara
                    m3u8 = find_m3u8_in_json(data)
                    if m3u8:
                        return m3u8
                except (json.JSONDecodeError, ValueError):
                    pass
                
                # Düz text response
                m3u8 = find_m3u8_direct(resp.text)
                if m3u8:
                    return m3u8
                    
        except Exception:
            continue
    
    return None


def find_m3u8_in_json(data, depth=0):
    """JSON veri yapısı içinde m3u8 URL'si ara"""
    if depth > 5:
        return None
    
    if isinstance(data, str):
        if '.m3u8' in data:
            return data
        return None
    
    if isinstance(data, dict):
        # Öncelikli anahtarlar
        priority_keys = ['url', 'src', 'source', 'stream', 'file',
                         'hls', 'stream_url', 'video_url', 'link', 'playUrl']
        
        for key in priority_keys:
            if key in data:
                result = find_m3u8_in_json(data[key], depth + 1)
                if result:
                    return result
        
        # Diğer anahtarlar
        for key, value in data.items():
            if key not in priority_keys:
                result = find_m3u8_in_json(value, depth + 1)
                if result:
                    return result
    
    if isinstance(data, list):
        for item in data:
            result = find_m3u8_in_json(item, depth + 1)
            if result:
                return result
    
    return None


def find_m3u8_from_player_page(base_url, channel_id, headers):
    """player.html veya embed sayfası üzerinden m3u8 bul"""
    player_patterns = [
        f"{base_url}/player.html?id={channel_id}",
        f"{base_url}/embed.html?id={channel_id}",
        f"{base_url}/watch.html?id={channel_id}",
        f"{base_url}/player/{channel_id}",
        f"{base_url}/embed/{channel_id}",
    ]
    
    for player_url in player_patterns:
        try:
            resp = requests.get(player_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                m3u8 = find_m3u8_direct(resp.text)
                if m3u8:
                    return m3u8
                m3u8 = find_m3u8_from_js_vars(resp.text)
                if m3u8:
                    return m3u8
        except Exception:
            continue
    
    return None


# ============================================================
# M3U DOSYA OLUŞTURMA
# ============================================================

def generate_m3u(playlist_entries):
    """M3U playlist dosyasını oluştur"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    lines = [
        '#EXTM3U',
        f'# Mahsun Sports Playlist',
        f'# Son güncelleme: {now}',
        f'# Toplam kanal: {len(playlist_entries)}',
        '',
    ]
    
    # Kanal grupları tanımla
    group_map = {
        'bein': 'BeIN Sports',
        'ssport': 'S Sport',
        'tivibu': 'Tivibu Spor',
        'smart': 'Smart Spor',
        'euro': 'Euro Sport',
        'trt': 'TRT',
        'exxen': 'Exxen',
        'tabi': 'Tabi Spor',
        'nba': 'NBA',
    }
    
    for entry in playlist_entries:
        title = entry['title']
        url = entry['url']
        
        # Grup belirleme
        group = 'Diğer'
        title_lower = title.lower().replace(' ', '')
        for key, grp in group_map.items():
            if key in title_lower:
                group = grp
                break
        
        # Logo URL'si (opsiyonel, boş bırakılabilir)
        logo = ""
        
        lines.append(
            f'#EXTINF:-1 tvg-name="{title}" '
            f'tvg-logo="{logo}" '
            f'group-title="{group}",{title}'
        )
        lines.append(url)
        lines.append('')
    
    content = '\n'.join(lines)
    
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"M3U dosyası oluşturuldu: {M3U_FILE} ({len(playlist_entries)} kanal)")
    return content


# ============================================================
# ANA İŞLEM
# ============================================================

def run():
    """Ana çalıştırma fonksiyonu"""
    logger.info("=" * 60)
    logger.info("Mahsun Sports M3U Playlist Generator başlatılıyor...")
    logger.info("=" * 60)
    
    # Durumu yükle
    state = load_state()
    logger.info(f"Mevcut base URL: {state.get('base_url', DEFAULT_BASE_URL)}")
    
    # Domain kontrolü
    logger.info("Domain kontrolü yapılıyor...")
    base_url = resolve_base_url(state)
    logger.info(f"Aktif base URL: {base_url}")
    
    # Bağlantı testi
    try:
        test_resp = requests.get(
            base_url,
            headers=get_headers(base_url),
            timeout=15
        )
        if test_resp.status_code != 200:
            logger.error(f"Site erişilemez! Status: {test_resp.status_code}")
            # Eski playlist'i koru, state'i kaydet
            save_state(state)
            return
    except requests.exceptions.RequestException as e:
        logger.error(f"Site bağlantı hatası: {e}")
        save_state(state)
        return
    
    # Kanal listesini güncelle
    logger.info("Kanal listesi alınıyor...")
    channels = fetch_script_channels(base_url, state)
    logger.info(f"Toplam {len(channels)} kanal işlenecek.")
    
    # Her kanaldan m3u8 linkini çıkar
    headers = get_headers(base_url)
    playlist_entries = []
    success_count = 0
    fail_count = 0
    
    for i, channel in enumerate(channels, 1):
        title = channel.get('title', 'Bilinmeyen')
        channel_id = channel.get('id')
        direct_url = channel.get('direct_url')
        
        logger.info(f"\n[{i}/{len(channels)}] {title}")
        
        if direct_url:
            # Doğrudan URL var
            playlist_entries.append({
                'title': title,
                'url': direct_url
            })
            success_count += 1
            continue
        
        if not channel_id:
            logger.warning(f"  Kanal ID'si yok, atlanıyor: {title}")
            fail_count += 1
            continue
        
        # m3u8 linkini çıkar
        m3u8_url = extract_m3u8_from_event_page(base_url, channel_id, headers)
        
        if m3u8_url:
            playlist_entries.append({
                'title': title,
                'url': m3u8_url
            })
            success_count += 1
        else:
            fail_count += 1
        
        # Rate limiting - siteyere yük bindirmemek için
        time.sleep(1.5)
    
    # Sonuçları logla
    logger.info("\n" + "=" * 60)
    logger.info(f"SONUÇ: {success_count} başarılı, {fail_count} başarısız")
    logger.info("=" * 60)
    
    # M3U dosyasını oluştur
    if playlist_entries:
        generate_m3u(playlist_entries)
    else:
        logger.error("Hiçbir m3u8 linki bulunamadı! Playlist oluşturulmadı.")
        # Eski playlist dosyasını koru
    
    # Durumu kaydet
    save_state(state)
    
    logger.info("İşlem tamamlandı.")


if __name__ == "__main__":
    run()
