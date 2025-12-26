import requests
from ..config import MS_SEARCH_AI

def search_ai(query: str) -> str:
    r = requests.get(MS_SEARCH_AI, params={"chat": query}, timeout=60)
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        data = r.json()
        for k in ("answer", "result", "message", "text", "data"):
            if k in data and isinstance(data[k], str):
                return data[k][:3500]
        return str(data)[:3500]
    return r.text[:3500]
