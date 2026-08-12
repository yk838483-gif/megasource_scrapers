"""
MegaSource Scraper - 4kHdHub
============================
Scrapes 4kHdHub for Movies and TV Series (Hindi, English, Multi-Audio).
Uses Python standard library (urllib + re + json).
"""

import datetime
import http.cookiejar
import json
import random
import re
import urllib.error
import urllib.parse
import urllib.request

# --- METADATA ---
TITLE = "4kHdHub"
VERSION = "1.0.0"
DESCRIPTION = "4kHdHub Scraper for Movies and TV Series"

TMDB_API_KEY = "307b7b8ef035c6aa336900aef4e203bd"
DOMAINS_JSON_URL = "https://codeberg.org/eclipsia-404/eclipsia/raw/branch/main/urls.json"
DEFAULT_BASE_URL = "https://4khdhub.one"

MOBILE_UAS = [
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

SESSION_UA = random.choice(MOBILE_UAS)
BASE_URL = DEFAULT_BASE_URL

# --- REGEX PATTERNS ---
RE_QUALITY = re.compile(r"(2160|1080|720|480)p|(4K|UHD)", re.I)
RE_YEAR = re.compile(r"\b(19\d{2}|20\d{2})\b")
RE_SIZE_CTX = re.compile(r"(?:^|[\s>])(\d+\.?\d*)\s*(GB|MB)\b", re.I)
RE_HUBCLOUD = re.compile(r"https?://hubcloud\.[a-z0-9]+/drive/[a-z0-9]+", re.I)
RE_SXEX = re.compile(r"S0*(\d+)[.\s_\-]*E0*(\d+)", re.I)
RE_EP = re.compile(r"Episode\s*0*(\d+)", re.I)
RE_HEADER = re.compile(r"<div[^>]*class=['\"][^'\"]*card-header[^'\"]*['\"][^>]*>([^<]+)<", re.I)
RE_SIZE_TD = re.compile(r"<td[^>]*>\s*File\s*Size\s*:\s*</td>\s*<td[^>]*>\s*([\d\.]+\s*[MGBtbi]+)\s*</td>", re.I)
RE_SIZE_STR = re.compile(r"Size\s*:\s*</strong>\s*([\d\.]+\s*[MGBtbi]+)", re.I)
RE_SLUG_JUNK = re.compile(r"^(movie|series)$|^\d+$", re.I)
RE_NONALNUM = re.compile(r"[^a-z0-9]")
RE_EXT = re.compile(r"\.(mkv|mp4|avi|rar|zip)$", re.I)
RE_ZIP_RAR = re.compile(r"\.zip|\.rar", re.I)
RE_PIXEL = re.compile(r"pixel\.hubcloud", re.I)

AUDIO_TABLE = [
    (re.compile(r"ddp.?51.*truehd.*71|truehd.*71.*ddp.?51", re.I), "DDP 5.1 + TrueHD 7.1"),
    (re.compile(r"ddp.?51.*ddp.?71|ddp.?71.*ddp.?51", re.I), "DDP 5.1 + DDP 7.1"),
    (re.compile(r"ddp.?51.*aac.?71|aac.?71.*ddp.?51", re.I), "DDP 5.1 + AAC 7.1"),
    (re.compile(r"ddp.?51", re.I), "DDP 5.1"),
    (re.compile(r"truehd", re.I), "TrueHD 7.1"),
    (re.compile(r"aac.*71|71.*aac", re.I), "AAC 7.1"),
    (re.compile(r"aac", re.I), "AAC 5.1"),
]

# --- HTTP HANDLERS ---
_cookiejar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookiejar))

def _request(url, headers=None):
    req_headers = {
        "User-Agent": SESSION_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers)
    try:
        with _opener.open(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception:
        return 0, ""

def refresh_domains():
    global BASE_URL
    status, body = _request(DOMAINS_JSON_URL, headers={"User-Agent": "Mozilla/5.0"})
    if status == 200 and body:
        try:
            data = json.loads(body)
            if "4khdhub" in data and data["4khdhub"]:
                BASE_URL = data["4khdhub"].rstrip("/")
        except Exception:
            pass

def get_tmdb_info(imdb_id):
    url = f"https://api.themoviedb.org/3/find/{urllib.parse.quote(imdb_id)}?api_key={TMDB_API_KEY}&external_source=imdb_id"
    status, body = _request(url)
    if status != 200 or not body:
        return None
    try:
        data = json.loads(body)
        if data.get("movie_results"):
            item = data["movie_results"][0]
            return {"title": item.get("title", ""), "year": (item.get("release_date") or "")[:4], "imdb_id": imdb_id, "type": "movie"}
        elif data.get("tv_results"):
            item = data["tv_results"][0]
            return {"title": item.get("name", ""), "year": (item.get("first_air_date") or "")[:4], "imdb_id": imdb_id, "type": "tv"}
    except Exception:
        pass
    return None

def search_site(title, year, imdb_id, is_series):
    if imdb_id:
        status, body = _request(f"{BASE_URL}/wp-json/wp/v2/posts?search={imdb_id}")
        if status == 200 and body:
            try:
                posts = json.loads(body)
                if posts and len(posts) > 0:
                    post = posts[0]
                    return {
                        "url": post.get("link"),
                        "title": post.get("title", {}).get("rendered", title),
                        "content": None if is_series else post.get("content", {}).get("rendered", "")
                    }
            except Exception:
                pass

    status, html = _request(f"{BASE_URL}/?s={urllib.parse.quote(title)}")
    if status != 200 or not html:
        return None

    body = html.split('id="main"')[1] if 'id="main"' in html else html
    clean_q = RE_NONALNUM.sub("", title.lower())
    type_str = "-series-" if is_series else "-movie-"
    anti_str = "-movie-" if is_series else "-series-"

    link_matches = re.finditer(r'href="(https?://[^"/]+)?(/[^"]+)"', body)
    best = None

    for m in link_matches:
        domain = m.group(1) or ""
        path = m.group(2)
        if domain and "4khdhub" not in domain:
            continue
        if "/category/" in path or "?" in path or anti_str in path:
            continue
        if type_str not in path:
            continue

        slug_words = [w for w in path.split("/") if w][-1].split("-")
        slug_clean = RE_NONALNUM.sub("", "".join([w for w in slug_words if not RE_SLUG_JUNK.match(w)]).lower())
        if clean_q not in slug_clean and slug_clean not in clean_q:
            continue

        ctx = body[m.start(): m.start() + 300]
        year_match = RE_YEAR.search(ctx)
        year_hit = year and year_match and year_match.group(1) == year

        if not best or year_hit:
            best = {"url": BASE_URL + path, "title": title}
            if year_hit:
                break

    return best

def extract_hubcloud_links(html, season, episode, is_series):
    results = []
    scope = html

    if is_series:
        start = html.find('id="episodes"')
        if start < 0:
            start = html.find('data-tab="episodes"')
        if start >= 0:
            scope = html[start:]
            end = scope.find('id="complete-pack"')
            if end >= 0:
                scope = scope[:end]

    for m in RE_HUBCLOUD.finditer(scope):
        url = m.group(0)
        idx = m.start()

        if is_series:
            ctx_before = scope[max(0, idx - 3000): idx]
            ctx_after = scope[idx: min(len(scope), idx + 500)]
            ctx = ctx_before + ctx_after

            ep_match = RE_SXEX.search(ctx) or RE_EP.search(ctx)
            if not ep_match:
                continue

            s = season
            if ep_match.group(2):
                s = int(ep_match.group(1))
                e = int(ep_match.group(2))
            else:
                e = int(ep_match.group(1))

            if s != season or e != episode:
                continue

            qm = RE_QUALITY.search(ctx_before)
            quality = "HD"
            if qm:
                v = qm.group(1) or qm.group(2)
                quality = "2160P" if v.upper() in ["4K", "UHD"] else v.upper() + "P"
            if quality == "480P":
                continue

            sm = RE_SIZE_CTX.search(ctx_before)
            size = f"{sm.group(1)} {sm.group(2)}" if sm else ""
            results.append({"url": url, "quality": quality, "size": size})

        else:
            context = scope[max(0, idx - 1500): idx]
            qm = RE_QUALITY.search(context)
            quality = "HD"
            if qm:
                v = qm.group(1) or qm.group(2)
                quality = "2160P" if v.upper() in ["4K", "UHD"] else v.upper() + "P"
            if quality == "480P":
                continue

            sm = RE_SIZE_CTX.search(context)
            size = f"{sm.group(1)} {sm.group(2)}" if sm else ""
            results.append({"url": url, "quality": quality, "size": size})

    return results

def make_stream(filename, source_name, stream_url, quality, host_label, referer, size):
    quality_up = (quality or "1080P").upper()
    encoded_url = stream_url.replace(" ", "%20")
    combined = f"{filename or ''} {source_name or ''} {encoded_url}".lower()

    lang_parts = []
    if re.search(r"\b(?:english|eng)\b", combined): lang_parts.append("English")
    if re.search(r"\bhindi\b", combined): lang_parts.append("Hindi")
    if re.search(r"\btamil\b", combined): lang_parts.append("Tamil")
    if re.search(r"\btelugu\b", combined): lang_parts.append("Telugu")

    source = "WEB-DL"
    if re.search(r"\bbluray\b", combined): source = "Blu-ray"
    elif re.search(r"\b(?:webrip|hdrip)\b", combined): source = "WEB-Rip"

    hdr_tag = ""
    if re.search(r"\bhdr10\+|hdr10p\b", combined): hdr_tag = "HDR10+"
    elif re.search(r"\bhdr10\b", combined): hdr_tag = "HDR10"
    elif re.search(r"\bhdr\b", combined): hdr_tag = "HDR"
    elif re.search(r"\bsdr\b", combined): hdr_tag = "SDR"

    bit10_tag = "10Bit" if re.search(r"\b10bit\b", combined) else ""
    dv_tag = "DV" if re.search(r"\b(?:dv|dolby\s*vision)\b", combined) else ""
    codec = "H.265" if re.search(r"\b(?:hevc|x265|265)\b", combined) or quality_up == "2160P" else "H.264"
    is_imax = bool(re.search(r"\bimax\b", combined))

    audio = "DDP 5.1"
    for pattern, label in AUDIO_TABLE:
        if pattern.search(combined):
            audio = label
            break
    if re.search(r"\batmos\b", combined):
        audio += " Atmos"

    main_title = " • ".join([f"{TITLE}", quality_up, size]).strip(" • ")
    line1 = " • ".join(lang_parts)
    line2 = " • ".join([x for x in [source, "IMAX" if is_imax else "", host_label or "FSL"] if x])
    line3 = " • ".join([x for x in [bit10_tag, dv_tag, hdr_tag, codec, audio] if x])
    stream_title = "\n".join([x for x in [line1, line2, line3] if x])

    return {
        "name": main_title,
        "title": stream_title,
        "url": encoded_url,
        "behaviorHints": {
            "notMyMetadata": True,
            "proxyHeaders": {
                "request": {
                    "User-Agent": SESSION_UA,
                    "Referer": referer or "https://4khdhub.one/",
                }
            },
        },
    }

def resolve_hubcloud(link, fallback_title):
    url = link["url"]
    quality = link["quality"]
    size = link["size"]
    streams = []

    status, html = _request(url, headers={"Referer": BASE_URL + "/"})
    if status != 200 or not html:
        return streams

    php_match = re.search(r'href="([^"]*hubcloud\.php[^"]*)"', html, re.I)
    if not php_match:
        return streams

    php_url = php_match.group(1).replace("&amp;", "&")
    status2, html2 = _request(php_url, headers={"Referer": url})
    if status2 != 200 or not html2:
        return streams

    hm = RE_HEADER.search(html2)
    filename = RE_EXT.sub("", hm.group(1).strip()) if hm else fallback_title
    file_size = size
    sm = RE_SIZE_TD.search(html2) or RE_SIZE_STR.search(html2)
    if sm:
        file_size = sm.group(1).strip()

    link_regex = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(?:<i[^>]*></i>)?\s*([^<]+)</a>', re.I)
    for m in link_regex.finditer(html2):
        stream_url = m.group(1).replace("&amp;", "&")
        label = m.group(2).strip()

        if not stream_url or stream_url.startswith("javascript:"): continue
        if RE_ZIP_RAR.search(stream_url) or RE_PIXEL.search(stream_url): continue
        if re.search(r"telegram", label, re.I) or re.search(r"tg/", stream_url, re.I): continue
        if re.search(r"hubcloud\.cx/drive/admin|pixeldrain|bzzhr", stream_url, re.I): continue

        host = ""
        if re.search(r"cdn\.fsl-buckets\.life|r2\.cloudflarestorage|r2\.dev", stream_url, re.I):
            host = "FSL-v2"
        elif re.search(r"hub\.(latent|whistle)", stream_url, re.I):
            host = "FSL"
            stream_url = f"{stream_url}1{datetime.datetime.now().minute}"
        else:
            continue

        streams.append(make_stream(filename, host, stream_url, quality, host, php_url, file_size))

    return streams

# --- MEGASOURCE PROTOCOL ENTRYPOINT ---

def get_streams(media_type, media_id, config=None):
    imdb_id = media_id
    season = episode = None

    if ":" in media_id:
        parts = media_id.split(":", 2)
        imdb_id, season, episode = parts[0], parts[1], parts[2]

    refresh_domains()
    info = get_tmdb_info(imdb_id)

    if not info or not info.get("title"):
        return []

    is_series = (media_type == "series")
    search_res = search_site(info["title"], info["year"], info["imdb_id"], is_series)

    if not search_res:
        return []

    if not is_series and search_res.get("content"):
        html = search_res["content"]
    else:
        status, html = _request(search_res["url"])
        if status != 200 or not html:
            return []

    s_num = int(season) if season else None
    e_num = int(episode) if episode else None

    links = extract_hubcloud_links(html, s_num, e_num, is_series)
    all_streams = []

    for link in links:
        resolved = resolve_hubcloud(link, info["title"])
        all_streams.extend(resolved)

    return all_streams
