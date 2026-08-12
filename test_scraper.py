"""
MegaSource Test Streams Scraper
================================
Scraper de TESTE para o addon MegaSource. Retorna links publicos de videos
de teste para QUALQUER filme ou serie (o ID pedido so entra no rotulo).

Protocolo
---------
    TITLE, VERSION, DESCRIPTION
    get_streams(media_type: str, media_id: str, config: dict | None) -> list[dict]

media_type : "movie" | "series"
media_id   : "tt0111161" (filme) | "tt0944947:1:1" (serie: temporada: episodio)

Uso
---
Suba este arquivo como scraper.py num repositório do GitHub e adicione a URL
raw na pagina de configuracao do MegaSource, junto com outros scrapers, para
testar com mais de um script.

Os links sao streams publicos de teste (HLS/DASH) — nenhum usa o bucket
Google (gtv-videos-bucket). So biblioteca padrao do Python.
"""

TITLE = "MegaSource Test Streams"
VERSION = "1.0.0"
DESCRIPTION = "Streams publicos de teste para qualquer filme/serie (sem googlevideo)"

TEST_STREAMS = [
    {
        "title": "Big Buck Bunny (Mux)",
        "url": "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
        "quality": "1080p",
        "format": "HLS",
    },
    {
        "title": "Tears of Steel (Unified Streaming)",
        "url": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.m3u8",
        "quality": "720p",
        "format": "HLS",
    },
    {
        "title": "Tears of Steel (Unified Streaming)",
        "url": "https://demo.unified-streaming.com/k8s/features/stable/video/tears-of-steel/tears-of-steel.ism/.mpd",
        "quality": "720p",
        "format": "DASH",
    },
    {
        "title": "Netflix Test Case (Akamai)",
        "url": "https://dash.akamaized.net/dash264/TestCases/1a/netflix/exMPD_BIP_TC1.mpd",
        "quality": "1080p",
        "format": "DASH",
    },
    {
        "title": "Akamai Live Test",
        "url": "https://moctobpltc-i.akamaihd.net/hls/live/571329/eight/playlist.m3u8",
        "quality": "720p",
        "format": "HLS",
    },
    {
        "title": "Akamai Test Master",
        "url": "https://cph-p2p-msl.akamaized.net/hls/live/2000341/test/master.m3u8",
        "quality": "720p",
        "format": "HLS",
    },
    {
        "title": "Apple HLS Example (BipBop)",
        "url": "https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_hevc/master.m3u8",
        "quality": "1080p",
        "format": "HLS",
    },
]


def get_streams(media_type, media_id, config=None):
    """Retorna os streams de teste para qualquer media."""
    label = media_id
    if ":" in media_id:
        parts = media_id.split(":", 2)
        label = f"{parts[0]} S{parts[1]}E{parts[2]}"

    only_format = None
    if isinstance(config, dict):
        only_format = config.get("format")

    streams = []
    for source in TEST_STREAMS:
        if only_format and source["format"] != only_format:
            continue
        streams.append(
            {
                "url": source["url"],
                "title": f"{TITLE} • {source['title']}",
                "quality": source.get("quality"),
                "source": source["title"],
                "name": f"{TITLE} ({source['format']})",
            }
        )

    if streams:
        streams[0]["title"] = f"{TITLE} • {label} • {streams[0]['source']}"

    return streams

