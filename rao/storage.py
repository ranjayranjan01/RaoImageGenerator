import os
import json
from typing import Any, Dict
from .config import DATA_DIR

def _p(name: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, name)

USERS_FILE = _p("users.json")
SETTINGS_FILE = _p("settings.json")
BANS_FILE = _p("bans.json")
STYLES_CACHE_FILE = _p("styles_cache.json")
USERNAME_CACHE_FILE = _p("username_cache.json")  # @username -> id mapping (only for users who've interacted)

def load_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_state() -> Dict[str, Any]:
    settings = load_json(SETTINGS_FILE, {
        "bot_enabled": True,
        "cooldown_seconds": 8,
        "daily_limit": 40,  # 0=unlimited

        "default_style": "Pointillism",
        "default_model": "flux",
        "models": ["flux", "sdxl"],
        "enhance_default": True,

        # Join Gate (multi)
        "join_gate_enabled": True,
        "join_gate_strict": True,
        "join_targets": [
            {"chat": "@Rinneganzone", "invite": "https://t.me/Rinneganzone"}
        ],

        # UI
        "ui_title": "Rao Image Generator",
        "ui_subtitle": "Elite AI Image Lab • Ultra HD • Pro UI",
        "footer": "Rao Lab • /gen /style /model • Root Protected",
        "maintenance_text": "🚧 Bot is temporarily OFF. Please try later.",

        # TTS
        "tts_default_voice": "",

        # Safety
        "max_prompt_len": 380,
    })

    users = load_json(USERS_FILE, {})
    bans = load_json(BANS_FILE, {"banned": []})
    styles_cache = load_json(STYLES_CACHE_FILE, {"styles": [], "ts": 0})
    uname_cache = load_json(USERNAME_CACHE_FILE, {})  # {"username": {"id":..., "name":..., "ts":...}}

    return {
        "settings": settings,
        "users": users,
        "bans": bans,
        "styles_cache": styles_cache,
        "uname_cache": uname_cache
    }

def persist_state(state: Dict[str, Any]) -> None:
    save_json(SETTINGS_FILE, state["settings"])
    save_json(USERS_FILE, state["users"])
    save_json(BANS_FILE, state["bans"])
    save_json(STYLES_CACHE_FILE, state["styles_cache"])
    save_json(USERNAME_CACHE_FILE, state["uname_cache"])
