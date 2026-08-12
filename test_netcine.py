# -*- coding: utf-8 -*-
"""
MegaSource - netcine
================================

Protocol
--------
Seguindo o protocolo do MegaSource, este arquivo define:

    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

media_type : "movie" | "series"
media_id   : "tt0111161" (filme) | "tt0944947:1:1" (serie: temporada: episodio)

Retorna streams com behaviorHints.proxyHeaders
Usa apenas a biblioteca padrao do Python (urllib + cookiejar).

Para usar: suba este arquivo como scraper.py num repositório do GitHub e
adicione a URL raw no addon MegaSource (pagina de configuracao).
"""
import requests
import re
import json
import time
import gzip
import logging
from io import BytesIO
from urllib.parse import urlparse, quote_plus, urljoin, unquote_plus, parse_qs
from bs4 import BeautifulSoup

# Configuração de logging apenas para ERROS
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

class CaptchaResolver:
    def __init__(self, HEADERS, COOKIES, PAGINA_INICIAL):
        self.headers = HEADERS.copy()
        self.cookies = COOKIES.copy()
        self.INICIAL = PAGINA_INICIAL
        
        self.headers_img = {
            'User-Agent': self.headers.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'),
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': self.INICIAL,
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-origin',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }

        self.headers_post = {
            'User-Agent': HEADERS['User-Agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': self.headers['Origin'],
            'Referer': self.INICIAL,
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Pragma': 'no-cache'
        }

        self.post_cookies = {"XCRF": "XCRF"}    
        self.image_cookie = {"XCRF": "XCRF"}
        if self.cookies.get("PHPSESSID"):
            self.image_cookie.update({'PHPSESSID': COOKIES['PHPSESSID']})
            self.post_cookies.update({'PHPSESSID': COOKIES['PHPSESSID']})

        self.padroes_m3u8 = [
            r'<source[^>]+src=["\']([^"\']+\.m3u8[^"\']*)["\'][^>]*>',
            r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
            r'(https?://[^\s"\']+[^"\']*-(?:ALTO|BAIXO)\.php\?token=[^\s"\']+)',
            r'(https?://[^\s"\']+[^"\']*\.php\?token=[^\s"\']+)',
            r'file:\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'src=["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
        ]

    def _decomprimir_resposta(self, resp):
        if resp.headers.get('Content-Encoding') == 'gzip':
            try:
                return gzip.decompress(resp.content).decode('utf-8', errors='ignore')
            except Exception:
                pass
        return resp.text

    def _extrair_link_m3u8(self, html):
        for padrao in self.padroes_m3u8:
            match = re.search(padrao, html, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
      
    def _limpar_texto_captcha(self, texto):
        return re.sub(r'[^A-Za-z0-9]', '', texto.strip())

    def _extrair_nome_da_url(self, url):
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        nome = params.get('n', [''])[0]
        if nome:
            nome = re.sub(r'(DUB|LEG)$', '', nome)
        return nome

    def _tem_form_captcha(self, html):
        if not html:
            return False
        return bool(
            re.search(r'name=["\']captcha_input["\']', html, re.I)
            or re.search(r'captcha_img', html, re.I)
            or re.search(r'Verifica[cç][aã]o Humana', html, re.I)
        )

    def resolver_captcha(self, max_tentativas=3):
        url_inicial = self.INICIAL

        sessao = requests.Session()
        sessao.headers.update(self.headers)
        sessao.cookies.update(self.cookies)
        sessao.verify = False
        sessao.headers.update({'Referer': url_inicial})

        for tentativa in range(1, max_tentativas + 1):
            try:
                resp = sessao.get(url_inicial, timeout=30)
                if resp.status_code not in (200, 403):
                    time.sleep(2)
                    continue
            except Exception as e:
                logging.error(f"Erro ao acessar URL: {e}")
                time.sleep(2)
                continue

            html = self._decomprimir_resposta(resp)

            link = self._extrair_link_m3u8(html)
            if link:
                return link

            if not self._tem_form_captcha(html):
                time.sleep(2)
                continue

            padrao_img = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
            imagens = re.findall(padrao_img, html, re.IGNORECASE)

            url_captcha = None
            for src in imagens:
                if 'captcha_img' in src:
                    url_captcha = urljoin(url_inicial, src)
                    break

            if not url_captcha:
                padroes_fallback = [
                    r'(https?://[^\s"\']+captcha_img=1[^\s"\']*)',
                    r'(/media-player/hls/hls\.php\?captcha_img=1[^\s"\']*)',
                    r'(\?captcha_img=1[^"\']*)',
                ]
                for padrao in padroes_fallback:
                    matches = re.findall(padrao, html)
                    if matches:
                        url_captcha = matches[0]
                        if url_captcha.startswith('/') or url_captcha.startswith('?'):
                            url_captcha = urljoin(url_inicial, url_captcha)
                        break

            if not url_captcha:
                time.sleep(2)
                continue

            self.headers_img['Referer'] = url_inicial

            try:
                resp_img = sessao.get(
                    url_captcha,
                    headers=self.headers_img,
                    cookies=self.image_cookie,
                    timeout=30,
                )
                if resp_img.status_code not in (200, 403):
                    time.sleep(2)
                    continue

                content_type = resp_img.headers.get('Content-Type', '').lower()
                if 'image' not in content_type and len(resp_img.content) < 500:
                    time.sleep(2)
                    continue

                imagem_bytes = BytesIO(resp_img.content)
            except Exception as e:
                logging.error(f"Erro ao baixar CAPTCHA: {e}")
                time.sleep(2)
                continue

            try:
                imagem_bytes.seek(0)
                files = {'file': ('captcha.png', imagem_bytes, 'image/png')}
                payload = {
                    'apikey': 'helloworld',
                    'language': 'eng',
                    'isOverlayRequired': False,
                }
                resp_ocr = requests.post(
                    'https://api.ocr.space/parse/image',
                    files=files,
                    data=payload,
                    timeout=30,
                )
                data = resp_ocr.json()
                if data.get('OCRExitCode') != 1:
                    time.sleep(2)
                    continue

                solucao = data['ParsedResults'][0]['ParsedText'].strip()
                solucao = self._limpar_texto_captcha(solucao)
                if not solucao:
                    time.sleep(2)
                    continue
            except Exception as e:
                logging.error(f"Erro no OCR: {e}")
                time.sleep(2)
                continue

            payload_post = {'captcha_input': solucao}
            self.headers_post['Referer'] = url_inicial

            try:
                resp_post = sessao.post(
                    url_inicial,
                    data=payload_post,
                    cookies=self.post_cookies,
                    headers=self.headers_post,
                    timeout=30,
                )
                if resp_post.status_code not in (200, 403):
                    time.sleep(2)
                    continue

                html_post = self._decomprimir_resposta(resp_post)
                link = self._extrair_link_m3u8(html_post)
                if link:
                    return link

                time.sleep(1.0)
                resp_recarregar = sessao.get(
                    url_inicial,
                    headers=self.headers,
                    timeout=30,
                )
                if resp_recarregar.status_code in (200, 403):
                    html_rec = self._decomprimir_resposta(resp_recarregar)
                    link = self._extrair_link_m3u8(html_rec)
                    if link:
                        return link
            except Exception as e:
                logging.error(f"Erro ao enviar solucao: {e}")
                time.sleep(2)
                continue

            time.sleep(3)

        return None


class TMDBConverter(object):
    def __init__(self, api_key='92c1507cc18d85290e7a0b96abb37316'):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"

    def buscar_por_imdb_id(self, imdb_id, idioma="pt-BR"):
        url = "%s/find/%s" % (self.base_url, imdb_id)
        params = {
            'api_key': self.api_key,
            'language': idioma,
            'external_source': 'imdb_id'
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            movie_results = data.get('movie_results', [])
            tv_results = data.get('tv_results', [])

            if not movie_results and not tv_results:
                return {'error': 'IMDb ID %s não encontrado' % imdb_id}

            if movie_results:
                item = movie_results[0]
                tipo = 'movie'
                tipo_nome = 'Filme'
            else:
                item = tv_results[0]
                tipo = 'tv'
                tipo_nome = 'Série'

            if tipo == 'tv':
                try:
                    detalhes = requests.get(
                        "%s/tv/%s" % (self.base_url, item['id']),
                        params={'api_key': self.api_key, 'language': idioma},
                        timeout=10
                    ).json()
                    inicio = detalhes.get('first_air_date', '')[:4]
                    fim = detalhes.get('last_air_date', '')[:4]
                    ano = inicio if inicio else 'N/A'
                    if fim and fim != inicio:
                        ano = "%s-%s" % (inicio, fim)
                except Exception:
                    ano = item.get('first_air_date', '')[:4] or 'N/A'
            else:
                ano = item.get('release_date', '')[:4] or 'N/A'

            try:
                ano = str(ano).split('-')[0]
            except:
                pass

            return {
                'imdb_id': imdb_id,
                'tmdb_id': item['id'],
                'tipo': tipo_nome,
                'titulo_br': item.get('title' if tipo == 'movie' else 'name', 'N/A'),
                'titulo_en': item.get('original_title' if tipo == 'movie' else 'original_name', 'N/A'),
                'ano': ano,
                'sinopse': item.get('overview', 'N/A'),
                'popularidade': item.get('popularity', 0)
            }
        except Exception as e:
            return {'error': str(e)}

class NetcineResolver:
    def __init__(self):         
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        })
        self.host = "https://zzz1.lat/"
        self.max_tentativas = 3

    def _imdb_info(self, imdb_id):
        try:                                 
            tmdb = TMDBConverter()
            busca = tmdb.buscar_por_imdb_id(imdb_id)
            if 'error' not in busca:
                return busca['titulo_br'], busca['titulo_en'], busca['ano']
            return None, None, None
        except Exception as e:
            logging.error("Erro ao buscar informações do IMDB: {}".format(e))
            return None, None, None

    def _search_netcine(self, query, year, is_series=False):
        if not query:
            return None
        
        query = query.replace("&amp;", "&")
        
        queries_to_try = [query]
        if query.lower().startswith('the '):
            queries_to_try.append(query[4:].strip())
        if 'The ' in query:
            queries_to_try.append(query.split('The ')[1].strip())
        if ':' in query:
            queries_to_try.append(query.split(":", 1)[1].strip())
            queries_to_try.append(query.split(":", 1)[0].strip())
        if ' e ' in query:
            queries_to_try.append(query.replace(' e ', ' & '))
        
        queries_to_try = list(dict.fromkeys(queries_to_try))
        
        for q in queries_to_try:
            if not q:
                continue
            try:
                search_url = "{}?s={}".format(self.host.rstrip("/"), quote_plus(q))
                r = self.session.get(search_url, timeout=12)
                soup = BeautifulSoup(r.text, "html.parser")
                items = soup.select("#box_movies .movie")
                if items:
                    break
            except:
                continue
        else:
            return None
        
        for item in items:
            a = item.select_one(".imagen a")
            if not a:
                continue

            if not is_series and "/tvshows/" in a["href"]:
                continue
            if is_series and "/tvshows/" not in a["href"]:
                continue

            title_tag = item.select_one("h2")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True).replace('–', '-')
            year_tag = item.select_one(".year")
            item_year = year_tag.get_text(strip=True).replace("–", "") if year_tag else ""

            query_lower = query.lower()
            title_lower = title.lower()
            
            def ano_bate():
                if not year:
                    return True
                try:
                    return (str(year) in item_year or 
                           str(int(year)+1) in item_year or 
                           str(int(year)-1) in item_year)
                except:
                    return str(year) in item_year
            
            if query_lower in title_lower and ano_bate():
                return a["href"]
            
            if query_lower.replace(" e ", " & ") in title_lower and ano_bate():
                return a["href"]
        
        return None

    def _get_player_links(self, page_url):
        try:
            r = self.session.get(page_url, timeout=12)
            soup = BeautifulSoup(r.text, "html.parser")

            links = {}
            menu = soup.select("#player-container .player-menu li a")

            for item in menu:
                text = item.get_text(strip=True).upper()
                tab_id = item["href"].replace("#", "")

                iframe = soup.select_one('#{} iframe'.format(tab_id))
                if not iframe:
                    continue

                src = iframe.get("src", "")
                if not src:
                    continue

                full_src = src if src.startswith("http") else self.host + src.lstrip("/")

                if "DUBLADO" in text:
                    links["dub"] = full_src
                elif "LEGENDADO" in text or "LEG" in text:
                    links["leg"] = full_src

            return links
        except Exception as e:
            logging.error("Erro ao obter players: {}".format(e))
            return {}

    def _resolve_stream(self, player_url):
        headers = {
            "Referer": player_url.split("/")[0] + "//" + player_url.split("/")[2] + "/",
            "Cookie": "XCRF=XCRF",
            "User-Agent": self.session.headers["User-Agent"],
            "Accept": "*/*",
            "Origin": self.host.rstrip("/"),
        }
        
        phpssesid = 'l109me6httocc9umt0017g98t5'
        try:
            r = self.session.get(player_url, headers=headers, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            player_url = soup.find('div', {'id': 'content'}).find_all('a')[0].get('href', '')
            phpssesid = r.cookies.get_dict().get('PHPSESSID', phpssesid)
        except Exception as e:
            logging.warning("Erro ao obter PHPSESSID: {}".format(e))

        URL_INICIAL = player_url

        COOKIES = {
            'PHPSESSID': phpssesid,
            '_ga': 'GA1.1.729318643.1786544601',
            '_ga_NZDPYDPLE0': 'GS2.1.s1786544601$o1$g0$t1786544601$j60$l0$h0'
        }            

        parsed = urlparse(URL_INICIAL)  
        base = f"{parsed.scheme}://{parsed.hostname}"
        URL_INICIAL = player_url.replace(base, "https://zzz1.lat")
        origin = 'https://zzz1.lat'

        HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Referer': origin + '/',
            'Origin': origin,
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Pragma': 'no-cache'
        }               

        resolver = CaptchaResolver(HEADERS, COOKIES, URL_INICIAL)
        stream_link = resolver.resolver_captcha(max_tentativas=3)
        
        if stream_link:
            stream_final = stream_link + "|User-Agent=" + headers["User-Agent"] + "&Referer=" + origin
            return stream_final, headers
        
        return None, headers

    def resolve(self, imdb_id, season, episode):
        imdb_id = str(imdb_id).strip()
        season = int(season) if season else None
        episode = int(episode) if episode else None
        
        title, title2, year = self._imdb_info(imdb_id)
        if not title and not title2 or not year:
            logging.error("Não foi possível obter informações do IMDb")
            return []

        is_series = season and episode
        
        page_url = self._search_netcine(title, year, is_series)
        if not page_url:
            page_url = self._search_netcine(title2, year, is_series)
            if not page_url:
                logging.error("Título não encontrado")
                return []

        streams = []

        if not is_series:
            players = self._get_player_links(page_url)
            for lang, url in players.items():
                stream_url, _ = self._resolve_stream(url)
                # fix to stremio
                stream_url = stream_url.split("|")[0]
                if stream_url:
                    streams.append({
                        "title": "Netcine • {} • {}".format(lang.upper(), title),
                        "stream": stream_url,
                        "User-Agent": _['User-Agent'],
                        "Origin": _['Origin'],
                        "Referer": _['Referer']
                        })
        else:
            try:
                r = self.session.get(page_url, timeout=12)
                soup = BeautifulSoup(r.text, "html.parser")
                seasons = soup.select("#cssmenu li.has-sub")
                
                if not seasons:
                    logging.error("Nenhuma temporada encontrada")
                    return streams
                
                if season > len(seasons):
                    logging.error("Temporada {} não encontrada (máx: {})".format(season, len(seasons)))
                    return streams
                
                season_block = seasons[season - 1]
                episodes = season_block.select("ul li")
                
                if episode > len(episodes):
                    logging.error("Episódio {} não encontrado (máx: {})".format(episode, len(episodes)))
                    return streams
                
                ep_block = episodes[episode - 1]
                ep_url = ep_block.select_one("a")["href"]

                players = self._get_player_links(ep_url)
                for lang, url in players.items():
                    stream_url, _ = self._resolve_stream(url)
                    # fix to stremio
                    stream_url = stream_url.split("|")[0]                    
                    if stream_url:
                        streams.append({
                            "title": "Netcine • {} • T{:02d}E{:02d}".format(lang.upper(), season, episode),
                            "stream": stream_url,
                            "User-Agent": _['User-Agent'],
                            "Origin": _['Origin'],
                            "Referer": _['Referer']
                        })
                        
            except IndexError as e:
                logging.error("Episódio não encontrado: T{}E{} - {}".format(season, episode, e))
            except Exception as e:
                logging.error("Erro ao buscar episódio: {}".format(e))

        return streams



def get_streams(media_type, media_id, config=None):
    imdb_id = media_id
    season = episode = None
    if ":" in media_id:
        parts = media_id.split(":", 2)
        imdb_id, season, episode = parts[0], parts[1], parts[2]

    resolver = NetcineResolver()

    if media_type == "movie":
        infos = resolver.resolve(imdb_id, season=None, episode=None)
    elif media_type == "series" and season and episode:
        infos = resolver.resolve(imdb_id, season=int(season), episode=int(episode))
    else:
        infos = {}

    if not infos:
        return []

    if infos:
        streams = []
        for info in infos:
            streams.append(
                {
                    "name": "NETCINE",
                    "title": info["title"],
                    "url": info["stream"],
                    "behaviorHints": {
                        "notMyMetadata": True,
                        "proxyHeaders": {
                            "request": {
                                "User-Agent": info["User-Agent"],
                                "Origin": info["Origin"],
                                "Referer": info["Referer"],
                            }
                        },
                    },
                }
            )            

        if streams:
            return streams

    return []    


# ==========================
# TESTE RÁPIDO
# ==========================
# if __name__ == "__main__":
#     streams = get_streams("movie","tt0133093")
#     print(streams)
