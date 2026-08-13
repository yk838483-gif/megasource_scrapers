# -*- coding: utf-8 -*-
"""
MegaSource - RedeFlix
================================

Protocol
--------
Seguindo o protocolo do MegaSource, este arquivo define:

    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

media_type : "movie" | "series"
media_id   : "tt0111161" (filme) | "tt0944947:1:1" (serie: temporada: episodio)

Retorna streams com behaviorHints.proxyHeaders
"""
import requests
import json
import re
import logging
from urllib.parse import urljoin

# Configuração de logging apenas para ERROS
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

TITLE = "RedeFlix"
VERSION = "1.0.0"
DESCRIPTION = "Filmes e Series do RedeFlix (watchplay)"

# Configurações
BASE_URL = "\x68\x74\x74\x70\x73\x3a\x2f\x2f\x76\x31\x2e\x77\x61\x74\x63\x68\x70\x6c\x61\x79\x2e\x73\x68\x6f\x70"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"

# Headers padrão
DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'User-Agent': USER_AGENT,
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
}

class RedeFlixResolver:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(DEFAULT_HEADERS)
        self.base_url = BASE_URL
        
    def _fetch_url(self, url):
        """Faz uma requisição HTTP e retorna o conteúdo"""
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                logging.error(f"HTTP {response.status_code} ao acessar {url}")
                return None
            return response.text
        except Exception as e:
            logging.error(f"Erro ao acessar {url}: {e}")
            return None
    
    def _extract_url_from_html(self, html, pattern):
        """Extrai URL do HTML usando padrão regex"""
        if not html:
            return None
        
        # Procura por pattern="url" no HTML
        regex = re.compile(r'{}\s*=\s*"([^"]*)"'.format(pattern), re.IGNORECASE)
        match = regex.search(html)
        
        if not match:
            # Tenta encontrar como atributo data-*
            regex = re.compile(r'data-{}\s*=\s*"([^"]*)"'.format(pattern), re.IGNORECASE)
            match = regex.search(html)
        
        if match:
            url = match.group(1).replace('\\/', '/')
            return url
        
        return None
    
    def _extract_streams(self, html, referer):
        """Extrai os streams do HTML"""
        if not html:
            return []
        
        streams = []
        
        # Busca URL dublado
        dub_url = self._extract_url_from_html(html, 'dub')
        # Busca URL legendado
        leg_url = self._extract_url_from_html(html, 'leg')
        
        # Se não encontrou com os padrões acima, tenta outros padrões
        if not dub_url and not leg_url:
            # Procura por URLs no formato geral
            url_pattern = r'(https?://[^\s"\']+\.m3u8[^\s"\']*)'
            urls = re.findall(url_pattern, html, re.IGNORECASE)
            
            # Procura por pistas de áudio no texto
            for url in urls:
                # Verifica se está próximo de texto "dublado"
                context_before = html[max(0, html.find(url) - 200):html.find(url)]
                if 'dublado' in context_before.lower() or 'dub' in context_before.lower():
                    dub_url = url
                elif 'legendado' in context_before.lower() or 'leg' in context_before.lower():
                    leg_url = url
                else:
                    # Se não tem indicação, coloca como dublado
                    dub_url = url
        
        # Adiciona stream dublado
        if dub_url:
            streams.append({
                "title": "RedeFlix • Dublado",
                "stream": dub_url,
                "User-Agent": USER_AGENT,
                "Origin": self.base_url,
                "Referer": referer
            })
        
        # Adiciona stream legendado
        if leg_url:
            streams.append({
                "title": "RedeFlix • Legendado",
                "stream": leg_url,
                "User-Agent": USER_AGENT,
                "Origin": self.base_url,
                "Referer": referer
            })
        
        return streams
    
    def _get_tmdb_id(self, imdb_id):
        """Converte IMDb ID para TMDB ID"""
        try:
            tmdb_api_key = "\x39\x32\x63\x31\x35\x30\x37\x63\x63\x31\x38\x64\x38\x35\x32\x39\x30\x65\x37\x61\x30\x62\x39\x36\x61\x62\x62\x33\x37\x33\x31\x36"
            url = f"https://api.themoviedb.org/3/find/{imdb_id}"
            params = {
                'api_key': tmdb_api_key,
                'external_source': 'imdb_id'
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            # Verifica filmes
            if data.get('movie_results'):
                return data['movie_results'][0]['id'], 'movie'
            
            # Verifica séries
            if data.get('tv_results'):
                return data['tv_results'][0]['id'], 'tv'
            
            return None, None
        except Exception as e:
            logging.error(f"Erro ao converter IMDb para TMDB: {e}")
            return None, None
    
    def resolve_movie(self, imdb_id):
        """Resolve streams para filme"""
        # Converte IMDb para TMDB
        tmdb_id, media_type = self._get_tmdb_id(imdb_id)
        if not tmdb_id:
            logging.error(f"TMDB ID não encontrado para {imdb_id}")
            return []
        
        # Constrói URL
        url = f"{self.base_url}/movie/{tmdb_id}"
        logging.info(f"Buscando filme: {url}")
        
        # Busca HTML
        html = self._fetch_url(url)
        if not html:
            return []
        
        # Extrai streams
        return self._extract_streams(html, url)
    
    def resolve_series(self, imdb_id, season, episode):
        """Resolve streams para série"""
        # Converte IMDb para TMDB
        tmdb_id, media_type = self._get_tmdb_id(imdb_id)
        if not tmdb_id:
            logging.error(f"TMDB ID não encontrado para {imdb_id}")
            return []
        
        # Constrói URL
        url = f"{self.base_url}/tv/{tmdb_id}/{season}/{episode}"
        logging.info(f"Buscando série: {url}")
        
        # Busca HTML
        html = self._fetch_url(url)
        if not html:
            return []
        
        # Extrai streams
        return self._extract_streams(html, url)


def get_streams(media_type, media_id, config=None):
    """
    Função principal do scraper - chamada pelo MegaSource
    
    Args:
        media_type: "movie" ou "series"
        media_id: ID do IMDb (ex: "tt0133093") ou com temporada/episódio (ex: "tt0944947:1:1")
        config: Configurações extras (opcional)
    
    Returns:
        Lista de streams no formato do MegaSource
    """
    # Parse do media_id
    imdb_id = media_id
    season = episode = None
    
    if ":" in media_id:
        parts = media_id.split(":", 2)
        imdb_id = parts[0]
        if len(parts) > 1:
            season = int(parts[1])
        if len(parts) > 2:
            episode = int(parts[2])
    
    resolver = RedeFlixResolver()
    
    # Busca streams conforme o tipo
    if media_type == "movie":
        streams_data = resolver.resolve_movie(imdb_id)
    elif media_type == "series" and season and episode:
        streams_data = resolver.resolve_series(imdb_id, season, episode)
    else:
        return []
    
    if not streams_data:
        return []
    
    # Formata para o padrão do MegaSource
    result = []
    for stream in streams_data:
        result.append({
            "name": TITLE,
            "title": stream.get("title", "RedeFlix"),
            "url": stream.get("stream", ""),
            "behaviorHints": {
                "notMyMetadata": True,
                "proxyHeaders": {
                    "request": {
                        "User-Agent": stream.get("User-Agent", USER_AGENT),
                        "Origin": stream.get("Origin", BASE_URL),
                        "Referer": stream.get("Referer", BASE_URL + "/"),
                    }
                },
            },
        })
    
    return result


# ==========================
# TESTE RÁPIDO
# ==========================
# if __name__ == "__main__":
#     import json
    
#     # Teste para filme
#     print("="*60)
#     print("TESTE FILME - Matrix")
#     print("="*60)
#     streams = get_streams("movie", "tt0133093")
#     print(json.dumps(streams, indent=2))
    
#     # Teste para série
#     print("\n" + "="*60)
#     print("TESTE SÉRIE - Game of Thrones T1E1")
#     print("="*60)
#     streams = get_streams("series", "tt0944947:1:1")
#     print(json.dumps(streams, indent=2))
