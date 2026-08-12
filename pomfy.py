"""
Pomfy Stream Scraper
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

import base64
import http.cookiejar
import json
import math
import re
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

# ============================================================
# CONSTANTES
# ============================================================

TITLE = "Pomfy Scraper"
VERSION = "1.0.0"
DESCRIPTION = "Filmes e Series - Pomfy Stream"

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36"
)

TMDB_API_KEY = "\x33\x36\x34\x34\x64\x64\x34\x39\x35\x30\x62\x36\x37\x63\x64\x38\x30\x36\x37\x62\x38\x37\x37\x32\x64\x65\x35\x37\x36\x64\x36\x62"

# Headers padrão
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": "https://pomfy.online/",
    "Sec-Fetch-Dest": "iframe",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Upgrade-Insecure-Requests": "1",
}

STREAM_HEADERS = {"Referer": "https://pomfy.online/"}

# ============================================================
# COOKIE JAR E OPENER
# ============================================================

_cookiejar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookiejar))


def _request(url: str, method: str = "GET", data=None, headers=None):
    """Função auxiliar para fazer requisições HTTP"""
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)

    body = None
    if method == "POST":
        if isinstance(data, dict):
            body = json.dumps(data).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        elif data is not None:
            body = data

    req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with _opener.open(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception:
        return 0, ""


# ============================================================
# BASE64 - DECODIFICAR E CODIFICAR
# ============================================================

def base64_decode(base64_string: str) -> bytes:
    """Decodifica Base64 URL-safe para bytes"""
    # Converte URL-safe para base64 padrão
    decoded = base64_string.replace("-", "+").replace("_", "/")

    # Adiciona padding se necessário
    while len(decoded) % 4 != 0:
        decoded += "="

    return base64.b64decode(decoded)


def base64_encode(data: bytes) -> str:
    """Codifica bytes para Base64 URL-safe"""
    return base64.b64encode(data).decode("utf-8").replace("+", "-").replace("/", "_").rstrip("=")


# ============================================================
# CONVERSÃO UTF-8
# ============================================================

def utf8_bytes_to_string(bytes_data: bytes) -> str:
    """Converte bytes UTF-8 para string"""
    try:
        return bytes_data.decode("utf-8")
    except UnicodeDecodeError:
        # Fallback para caracteres inválidos
        return bytes_data.decode("utf-8", errors="replace")


def string_to_utf8_bytes(text: str) -> bytes:
    """Converte string para bytes UTF-8"""
    return text.encode("utf-8")


# ============================================================
# AES-256 (Rijndael) - IMPLEMENTAÇÃO
# ============================================================

# S-Box do AES
SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5,
    0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0,
    0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc,
    0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a,
    0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0,
    0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b,
    0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85,
    0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5,
    0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17,
    0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88,
    0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c,
    0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9,
    0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6,
    0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e,
    0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94,
    0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68,
    0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]

RCON = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


class AESCipher:
    """Implementação AES-256 em modo CTR"""

    def __init__(self, key_bytes: bytes):
        self.round_keys = self._expand_key(key_bytes)

    def _expand_key(self, key: bytes) -> list:
        """Expande a chave de 32 bytes para 60 palavras (240 bytes)"""
        round_keys = [0] * 60

        # Copia a chave inicial
        for i in range(8):
            round_keys[i] = struct.unpack(">I", key[i * 4:(i + 1) * 4])[0]

        for i in range(8, 60):
            temp = round_keys[i - 1]

            if i % 8 == 0:
                # RotWord
                temp = ((temp << 8) | (temp >> 24)) & 0xFFFFFFFF
                # SubWord
                temp = (
                    (SBOX[temp >> 24] << 24) |
                    (SBOX[(temp >> 16) & 0xFF] << 16) |
                    (SBOX[(temp >> 8) & 0xFF] << 8) |
                    SBOX[temp & 0xFF]
                )
                # XOR com RCON
                temp ^= RCON[i // 8] << 24
            elif i % 8 == 4:
                # SubWord
                temp = (
                    (SBOX[temp >> 24] << 24) |
                    (SBOX[(temp >> 16) & 0xFF] << 16) |
                    (SBOX[(temp >> 8) & 0xFF] << 8) |
                    SBOX[temp & 0xFF]
                )

            round_keys[i] = (round_keys[i - 8] ^ temp) & 0xFFFFFFFF

        return round_keys

    def _galois_multiply(self, a: int, b: int) -> int:
        """Multiplicação no campo de Galois GF(2^8)"""
        result = 0

        for _ in range(8):
            if b & 1:
                result ^= a

            carry = a & 0x80
            a = (a << 1) & 0xFF

            if carry:
                a ^= 0x1B

            b >>= 1

        return result

    def _encrypt_block(self, block: bytes) -> bytes:
        """Criptografa um bloco de 16 bytes"""
        # Converte para matriz state (linhas x colunas)
        state = [
            [block[0], block[4], block[8], block[12]],
            [block[1], block[5], block[9], block[13]],
            [block[2], block[6], block[10], block[14]],
            [block[3], block[7], block[11], block[15]]
        ]

        def add_round_key(state, round_num):
            for col in range(4):
                round_key = self.round_keys[round_num * 4 + col]
                for row in range(4):
                    state[row][col] ^= (round_key >> (24 - 8 * row)) & 0xFF

        # Round 0 - AddRoundKey
        add_round_key(state, 0)

        # Rounds 1 a 13
        for round_num in range(1, 14):
            # SubBytes
            for row in range(4):
                for col in range(4):
                    state[row][col] = SBOX[state[row][col]]

            # ShiftRows
            state[1] = [state[1][1], state[1][2], state[1][3], state[1][0]]
            state[2] = [state[2][2], state[2][3], state[2][0], state[2][1]]
            state[3] = [state[3][3], state[3][0], state[3][1], state[3][2]]

            # MixColumns
            for col in range(4):
                a = state[0][col]
                b = state[1][col]
                c = state[2][col]
                d = state[3][col]

                state[0][col] = (
                    self._galois_multiply(2, a) ^
                    self._galois_multiply(3, b) ^
                    c ^ d
                )
                state[1][col] = (
                    a ^
                    self._galois_multiply(2, b) ^
                    self._galois_multiply(3, c) ^
                    d
                )
                state[2][col] = (
                    a ^
                    b ^
                    self._galois_multiply(2, c) ^
                    self._galois_multiply(3, d)
                )
                state[3][col] = (
                    self._galois_multiply(3, a) ^
                    b ^
                    c ^
                    self._galois_multiply(2, d)
                )

            # AddRoundKey
            add_round_key(state, round_num)

        # Round 14 (final - sem MixColumns)
        for row in range(4):
            for col in range(4):
                state[row][col] = SBOX[state[row][col]]

        state[1] = [state[1][1], state[1][2], state[1][3], state[1][0]]
        state[2] = [state[2][2], state[2][3], state[2][0], state[2][1]]
        state[3] = [state[3][3], state[3][0], state[3][1], state[3][2]]

        add_round_key(state, 14)

        # Converte de volta para bytes
        result = bytearray(16)
        for col in range(4):
            for row in range(4):
                result[col * 4 + row] = state[row][col]

        return bytes(result)

    def decrypt(self, iv: bytes, ciphertext: bytes) -> str:
        """Descriptografa usando modo CTR"""
        # CTR mode - contador começa com IV + nonce
        counter = bytearray(16)
        counter[:len(iv)] = iv
        counter[15] = 2  # Nonce fixo

        plaintext = bytearray(len(ciphertext))

        for i in range(0, len(ciphertext), 16):
            # Gera keystream
            keystream = self._encrypt_block(bytes(counter))

            # XOR com o ciphertext
            block_size = min(16, len(ciphertext) - i)
            for j in range(block_size):
                plaintext[i + j] = ciphertext[i + j] ^ keystream[j]

            # Incrementa o contador (apenas os últimos 4 bytes)
            for k in range(15, 11, -1):
                counter[k] += 1
                if counter[k] != 0:
                    break

        return utf8_bytes_to_string(bytes(plaintext))


# ============================================================
# SELEÇÃO DE PARTES DA CHAVE
# ============================================================

def _get_key_mapping() -> dict:
    """Gera o mapeamento de versão para índices"""
    mapping = {}
    for i in range(1, 31):
        a = i ^ 0
        b = 31 - i ^ 0
        mapping[str(i)] = [a, b]
    return mapping


def _get_indices(version: int, total_parts: int) -> list:
    """Obtém os índices baseado na versão"""
    mapping = _get_key_mapping()
    indices = mapping.get(str(version), [])

    if not indices or not isinstance(indices, list):
        return []

    result = []
    for idx in indices:
        if 1 <= idx <= total_parts:
            result.append(idx - 1)

    return result


def _select_key_parts(data: dict) -> list:
    """Seleciona as partes da chave baseado na versão"""
    key_parts = data.get("key_parts", [])
    if not isinstance(key_parts, list):
        key_parts = []

    indices = _get_indices(data.get("version", 0), len(key_parts))

    if not indices:
        return key_parts[:2]

    selected = []
    for idx in indices:
        part = key_parts[idx] if idx < len(key_parts) else None
        if part and len(part) > 0:
            selected.append(part)

    return selected if selected else key_parts[:2]


def _build_key(data: dict) -> bytes:
    """Constrói a chave de 32 bytes a partir das partes"""
    selected_parts = _select_key_parts(data)
    decoded_parts = [base64_decode(part) for part in selected_parts]

    combined = b"".join(decoded_parts)

    # A chave deve ter 32 bytes (256 bits)
    if len(combined) > 32:
        return combined[:32]

    return combined


# ============================================================
# DECODIFICAÇÃO DO PLAYBACK
# ============================================================

def decode_playback(playback_data: dict) -> dict:
    """Decodifica os dados do playback para obter a URL"""
    try:
        key = _build_key(playback_data)
        iv = base64_decode(playback_data.get("iv", ""))
        payload = base64_decode(playback_data.get("payload", ""))

        # Remove o último bloco (16 bytes) que é o HMAC/tag
        ciphertext = payload[:-16]

        cipher = AESCipher(key)
        decrypted_text = cipher.decrypt(iv, ciphertext)

        json_data = json.loads(decrypted_text)

        # Extrai a URL
        url = (
            json_data.get("url") or
            (json_data.get("sources") and json_data["sources"][0].get("url")) or
            (json_data.get("data") and json_data["data"].get("sources") and
             json_data["data"]["sources"][0].get("url"))
        )

        if url:
            return {
                "success": True,
                "url": url.replace("\\u0026", "&")
            }

        return {"success": False, "error": "URL não encontrada"}

    except Exception as error:
        return {"success": False, "error": str(error)}


# ============================================================
# GERAÇÃO DE FINGERPRINT
# ============================================================

def _random_hex_string(length: int) -> str:
    """Gera uma string hexadecimal aleatória"""
    import random
    chars = "abcdef0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def generate_fingerprint() -> dict:
    """Gera o fingerprint para autenticação"""
    viewer_id = _random_hex_string(32)
    device_id = _random_hex_string(32)
    timestamp = int(time.time())

    payload = {
        "viewer_id": viewer_id,
        "device_id": device_id,
        "confidence": 0.93,
        "iat": timestamp,
        "exp": timestamp + 600  # 10 minutos
    }

    json_string = json.dumps(payload)
    utf8_bytes = string_to_utf8_bytes(json_string)
    token = base64_encode(utf8_bytes)

    return {
        "token": token,
        "viewer_id": viewer_id,
        "device_id": device_id,
        "confidence": 0.93
    }


# ============================================================
# BUSCA NO TMDB
# ============================================================

def imdb_to_tmdb(imdb_id: str, media_type: str = "movie") -> Optional[int]:
    """Converte ID IMDB para TMDB"""
    url = (
        f"https://api.themoviedb.org/3/find/{imdb_id}"
        f"?api_key={TMDB_API_KEY}&external_source=imdb_id"
    )

    status, body = _request(url, headers={"Accept": "application/json"})

    if status != 200:
        return None

    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None

    if media_type == "movie":
        results = data.get("movie_results", [])
    else:
        results = data.get("tv_results", [])

    if results and len(results) > 0:
        return results[0].get("id")

    return None


# ============================================================
# FUNÇÃO PRINCIPAL: get_streams
# ============================================================

def get_streams(media_type: str, media_id: str, config: dict = None) -> list:
    """
    Obtém os streams para um filme ou série

    Args:
        media_type: "movie" ou "series"
        media_id: "tt0111161" ou "tt0944947:1:1"
        config: Configuração opcional

    Returns:
        Lista de streams com informações do vídeo
    """
    # Parseia media_id
    imdb_id = media_id
    season = None
    episode = None

    if ":" in media_id:
        parts = media_id.split(":", 2)
        imdb_id = parts[0]
        if len(parts) > 1:
            season = parts[1]
        if len(parts) > 2:
            episode = parts[2]

    try:
        # ============================================================
        # PASSO 1: Converte IMDB para TMDB se necessário
        # ============================================================

        tmdb_id = None
        if imdb_id.lower().startswith("tt"):
            tmdb_id = imdb_to_tmdb(imdb_id, media_type)
            if not tmdb_id:
                return []
        else:
            tmdb_id = imdb_id

        # ============================================================
        # PASSO 2: Obtém a página do filme/série
        # ============================================================

        if media_type == "movie":
            page_url = f"https://api.pomfy.stream/filme/{tmdb_id}"
        else:
            season = int(season) if season else 1
            episode = int(episode) if episode else 1
            page_url = f"https://api.pomfy.stream/serie/{tmdb_id}/{season}/{episode}"

        status, page_html = _request(page_url, headers=DEFAULT_HEADERS)

        if status != 200:
            return []

        # ============================================================
        # PASSO 3: Extrai o statusToken do HTML
        # ============================================================

        status_token = None

        token_patterns = [
            r'const statusToken="([^"]+)"',
            r'statusToken["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'["\']statusToken["\']\s*:\s*["\']([^"\']+)["\']'
        ]

        for pattern in token_patterns:
            match = re.search(pattern, page_html)
            if match and match.group(1):
                status_token = match.group(1)
                break

        if not status_token:
            return []

        # ============================================================
        # PASSO 4: Obtém o byseUrl
        # ============================================================

        token_url = f"https://api.pomfy.stream/api/play-token?t={status_token}"

        token_headers = {
            "accept": "*/*",
            "cookie": "SITE_TOTAL_ID=aTYqe6GU65PNmeCXpelwJwAAAMi; __dtsu=104017651574995957BEB724C6373F9E; __cc_id=a44d1e52993b9c2Oaaf40eba24989a06",
            "referer": page_url,
            "user-agent": USER_AGENT
        }

        status, token_body = _request(token_url, headers=token_headers)

        if status != 200:
            return []

        try:
            token_data = json.loads(token_body)
        except (ValueError, TypeError):
            return []

        byse_url = token_data.get("byseUrl")

        if not byse_url:
            return []

        # ============================================================
        # PASSO 5: Obtém o embed_frame_url
        # ============================================================

        video_id = byse_url.split("/")[-1]
        details_url = f"https://pomfy-cdn.shop/api/videos/{video_id}/embed/details"

        details_headers = {
            "referer": byse_url,
            "x-embed-origin": "api.pomfy.stream",
            "user-agent": USER_AGENT
        }

        status, details_body = _request(details_url, headers=details_headers)

        if status != 200:
            return []

        try:
            details_data = json.loads(details_body)
        except (ValueError, TypeError):
            return []

        embed_frame_url = details_data.get("embed_frame_url")

        if not embed_frame_url:
            return []

        # ============================================================
        # PASSO 6: Gera fingerprint e faz POST para obter o playback
        # ============================================================

        # Extrai o origin da URL
        parsed_url = urllib.parse.urlparse(embed_frame_url)
        origin_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        fingerprint = generate_fingerprint()

        playback_url = f"{origin_url}/api/videos/{video_id}/embed/playback"

        playback_headers = {
            "content-type": "application/json",
            "origin": origin_url,
            "referer": embed_frame_url,
            "user-agent": USER_AGENT,
            "x-embed-origin": "api.pomfy.stream",
            "x-embed-parent": byse_url
        }

        playback_payload = {"fingerprint": fingerprint}

        status, playback_body = _request(
            playback_url,
            method="POST",
            data=playback_payload,
            headers=playback_headers
        )

        if status != 200:
            return []

        try:
            playback_data = json.loads(playback_body)
        except (ValueError, TypeError):
            return []

        if not playback_data.get("playback"):
            return []

        # ============================================================
        # PASSO 7: Decodifica o playback e extrai a URL
        # ============================================================

        decoded = decode_playback(playback_data["playback"])

        if not decoded.get("success"):
            return []

        # ============================================================
        # RETORNA O STREAM
        # ============================================================

        return [
            {
                "name": TITLE,
                "title": "1080P",
                "url": decoded["url"],
                "behaviorHints": {
                    "notMyMetadata": True,
                    "proxyHeaders": {
                        "request": STREAM_HEADERS
                    }
                },
            }
        ]

    except Exception:
        return []
