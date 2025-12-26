import requests
from typing import List
from ..config import STYLES_API
from ..utils import style_display, now_ts

def load_styles(cache: dict) -> List[str]:
    styles = cache.get("styles", [])
    ts = int(cache.get("ts", 0))
    if isinstance(styles, list) and styles and (now_ts() - ts) < 86400:
        return [style_display(str(s)) for s in styles]

    try:
        r = requests.get(STYLES_API, timeout=25)
        r.raise_for_status()
        data = r.json()
        raw = data.get("styles", [])
        if isinstance(raw, list) and raw:
            cache["styles"] = raw
            cache["ts"] = int(data.get("ts", now_ts()))
            return [style_display(str(s)) for s in raw]
    except Exception:
        pass

    return [
        "Pointillism", "Typography", "Line Art", "Caricature", "Adorable Kawaii",
        "Watercolor", "Manga", "Surreal Painting", "Pixel Art", "Sticker", "Tlingit Art"
    ]
