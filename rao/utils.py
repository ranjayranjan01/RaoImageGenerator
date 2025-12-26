import re
import time
from urllib.parse import quote_plus

MAX_PROMPT_LEN = 380

def now_ts() -> int:
    return int(time.time())

def today_str() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())

def trim_prompt(text: str) -> str:
    t = (text or "").strip()
    return t[:MAX_PROMPT_LEN]

def human_time(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"

def style_display(name: str) -> str:
    # "tlingit_art" -> "Tlingit Art"
    s = (name or "").strip().replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s.title()

def style_api(name: str) -> str:
    # "Tlingit Art" -> "tlingit_art"
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s

def build_image_url(base: str, prompt: str, model: str, style_title: str) -> str:
    return (
        f"{base}?prompt={quote_plus(trim_prompt(prompt))}"
        f"&model={quote_plus(model)}"
        f"&style={quote_plus(style_api(style_title))}"
    )

def enhance_prompt(prompt: str) -> str:
    extra = " ultra detailed, sharp focus, high quality, 4k, masterpiece, best quality, photorealistic"
    p = (prompt or "").strip()
    if not p:
        return p
    low = p.lower()
    if "masterpiece" in low or "ultra detailed" in low:
        return p
    return p + extra

def clean_username(text: str) -> str:
    t = (text or "").strip()
    t = t.replace("@", "").strip()
    return t.lower()
