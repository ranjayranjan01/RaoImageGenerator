import requests
from ..config import TTS_API

def get_voices() -> list:
    # if API returns list when text missing
    r = requests.get(TTS_API, timeout=30)
    r.raise_for_status()
    try:
        data = r.json()
    except Exception:
        return []
    if isinstance(data, list):
        return data
    for k in ("voices", "voice_names", "data"):
        if k in data and isinstance(data[k], list):
            return data[k]
    return []

def tts_audio_bytes(text: str, voice: str) -> bytes:
    # GET with params
    r = requests.get(TTS_API, params={"text": text, "voice": voice}, timeout=60)
    r.raise_for_status()

    ctype = (r.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        j = r.json()
        url = j.get("url") or j.get("audio") or j.get("result") or ""
        if not url:
            raise RuntimeError("TTS API returned JSON but no audio url.")
        rr = requests.get(url, timeout=60)
        rr.raise_for_status()
        return rr.content

    return r.content
