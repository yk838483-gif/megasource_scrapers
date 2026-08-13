"""
MegaSource Scraper - RogMovies
==============================
Scrapes RogMovies for Movies and TV Series.
Uses Python standard library (urllib, re, json, base64).
"""

import base64
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request

# --- METADATA ---
TITLE = "RogMovies"
VERSION = "1.0.0"
DESCRIPTION = "RogMovies Scraper for Movies and TV Series"

DEFAULT_MAIN_URL = "https://rogmovies.vip"
URLS_JSON_URL = "https://raw.githubusercontent.com/SaurabhKaperwan/Utils/refs/heads/main/urls.json"
CINEMETA_URL = "https://v3-cinemeta.strem.io/meta"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Global dynamic URLs
MAIN_URL = DEFAULT_MAIN_URL
VCLOUD_BASE = "https://vcloud.lol"
HUBCLOUD_BASE = "https://hubcloud.one"

# --- HTTP HANDLERS ---
_cookiejar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookiejar))

def _request(url, method="GET", data=None, headers=None, allow_redirects=True):
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)

    body = None
    if method == "POST":
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
        elif data is not None:
            body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with _opener.open(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), resp.geturl(), resp.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace"), exc.geturl(), exc.headers
    except Exception:
        return 0, "", "", {}

def update_dynamic_urls():
    global MAIN_URL, VCLOUD_BASE, HUBCLOUD_BASE
    status, body, _, _ = _request(URLS_JSON_URL)
    if status == 200 and body:
        try:
            data = json.loads(body)
            if data.get("rogmovies"):
                MAIN_URL = data["rogmovies"].rstrip("/")
            if data.get("vcloud"):
                VCLOUD_BASE = data["vcloud"].rstrip("/")
            if data.get("hubcloud"):
                HUBCLOUD_BASE = data["hubcloud"].rstrip("/")
        except Exception:
            pass

def get_cinemeta_info(media_type, imdb_id):
    c_type = "series" if media_type == "series" else "movie"
    url = f"{CINEMETA_URL}/{c_type}/{imdb_id}.json"
    status, body, _, _ = _request(url)
    if status == 200 and body:
        try:
            data = json.loads(body)
            meta = data.get("meta", {})
            return {
                "name": meta.get("name", ""),
                "year": meta.get("year", ""),
            }
        except Exception:
            pass
    return None

def extract_double_atob(html):
    match = re.search(r"atob\s*\(\s*atob\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\)", html)
    if match:
        try:
            step1 = base64.b64decode(match.group(1)).decode("utf-8")
            step2 = base64.b64decode(step1).decode("utf-8")
            return step2
        except Exception:
            pass
    return None

def resolve_vcloud(vcloud_url):
    base_domain = f"{urllib.parse.urlparse(vcloud_url).scheme}://{urllib.parse.urlparse(vcloud_url).netloc}"
    target_base = HUBCLOUD_BASE if "hubcloud" in vcloud_url else VCLOUD_BASE
    
    current_url = vcloud_url
    if base_domain != target_base:
        current_url = vcloud_url.replace(base_domain, target_base)
        base_domain = target_base

    status, html, _, _ = _request(current_url)
    if status != 200 or not html:
        return []

    link = ""
    if "/video/" in current_url:
        match = re.search(r'<div[^>]*class=["\']vd["\'][^>]*>\s*<center>\s*<a[^>]+href=["\']([^"\']+)["\']', html, re.I)
        if match:
            link = match.group(1)
    else:
        script_match = re.search(r"<script[^>]*>(.*?url.*?)</script>", html, re.S | re.I)
        script_text = script_match.group(1) if script_match else html
        
        if "vcloud" in current_url:
            link = extract_double_atob(script_text) or ""
        else:
            m = re.search(r"var\s+url\s*=\s*['\"]([^'\"]+)['\"]", script_text)
            if m:
                link = m.group(1)

    if not link:
        return []

    if not link.startswith("http"):
        link = base_domain + link

    status_doc, html_doc, _, _ = _request(link)
    if status_doc != 200 or not html_doc:
        return []

    header_match = re.search(r'<div[^>]*class=["\']card-header["\'][^>]*>(.*?)</div>', html_doc, re.S | re.I)
    header_text = re.sub(r"<[^>]+>", "", header_match.group(1)).strip() if header_match else "Stream"

    size_match = re.search(r'<i[^>]*id=["\']size["\'][^>]*>(.*?)</i>', html_doc, re.S | re.I)
    size_text = re.sub(r"<[^>]+>", "", size_match.group(1)).strip() if size_match else ""

    streams = []
    btn_matches = re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_doc, re.S | re.I)

    for btn in btn_matches:
        stream_link = btn.group(1)
        btn_text = re.sub(r"<[^>]+>", "", btn.group(2)).strip()
        server_label = ""

        if "FSL Server" in btn_text: server_label = "FSL Server"
        elif "FSLv2" in btn_text: server_label = "FSLv2 Server"
        elif "Mega Server" in btn_text: server_label = "Mega Server"
        elif "Download File" in btn_text: server_label = "Download File"
        elif "pixeldra" in stream_link:
            pxl_match = re.search(r"var\s+pxl\s*=\s*['\"]([^'\"]+)['\"]", html_doc)
            if pxl_match:
                pxl_url = pxl_match.group(1)
                pxl_base = f"{urllib.parse.urlparse(pxl_url).scheme}://{urllib.parse.urlparse(pxl_url).netloc}"
                if "download" in pxl_url.lower():
                    stream_link = pxl_url
                else:
                    file_id = pxl_url.rstrip("/").split("/")[-1]
                    stream_link = f"{pxl_base}/api/file/{file_id}?download"
                server_label = "Pixeldrain"
        
        if server_label and stream_link.startswith("http"):
            streams.append({
                "name": TITLE,
                "title": f"[{server_label}] {header_text} [{size_text}]",
                "url": stream_link,
                "behaviorHints": {
                    "notMyMetadata": True,
                    "proxyHeaders": {"request": {"User-Agent": USER_AGENT}}
                }
            })

    return streams

# --- MEGASOURCE ENTRYPOINT ---

def get_streams(media_type, media_id, config=None):
    imdb_id = media_id
    season = episode = None

    if ":" in media_id:
        parts = media_id.split(":", 2)
        imdb_id, season, episode = parts[0], int(parts[1]), int(parts[2])

    update_dynamic_urls()
    meta_info = get_cinemeta_info(media_type, imdb_id)
    query_title = meta_info["name"] if meta_info and meta_info.get("name") else imdb_id

    search_url = f"{MAIN_URL}/search.php?q={urllib.parse.quote(query_title)}&page=1"
    status, json_str, _, _ = _request(search_url)

    if status != 200 or not json_str:
        return []

    try:
        search_data = json.loads(json_str)
        hits = search_data.get("hits", [])
    except Exception:
        return []

    if not hits:
        return []

    target_post_url = hits[0].get("document", {}).get("permalink")
    if not target_post_url:
        return []

    status_post, post_html, _, _ = _request(target_post_url)
    if status_post != 200 or not post_html:
        return []

    vcloud_urls = []

    if media_type == "movie":
        btn_links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*<button[^>]*class=["\'][^"\']*dwd-button[^"\']*["\']', post_html, re.I)
        for btn_link in btn_links:
            st, page_html, _, _ = _request(btn_link)
            if st == 200 and page_html:
                m = re.search(r'<a[^>]+href=["\']([^"\']*vcloud[^"\']*)["\']', page_html, re.I)
                if m:
                    vcloud_urls.append(m.group(1))

    elif media_type == "series" and season and episode:
        season_pattern = re.compile(rf"(?:Season\s*|S){season}\b", re.I)
        if season_pattern.search(post_html):
            ep_links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', post_html, re.I)
            for href, text in ep_links:
                if "V-Cloud" in text or "Download" in text or "G-Direct" in text:
                    st, ep_page_html, _, _ = _request(href)
                    if st == 200 and ep_page_html:
                        v_links = re.findall(r'<a[^>]+href=["\']([^"\']*vcloud[^"\']*)["\']', ep_page_html, re.I)
                        if len(v_links) >= episode:
                            vcloud_urls.append(v_links[episode - 1])

    all_streams = []
    for v_url in vcloud_urls:
        res_streams = resolve_vcloud(v_url)
        all_streams.extend(res_streams)

    return all_streams
