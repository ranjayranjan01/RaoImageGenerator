from ..config import BOT_NAME

def panel_text(settings: dict, user: dict) -> str:
    style = user.get("style", settings.get("default_style","Pointillism"))
    model = user.get("model", settings.get("default_model","flux"))
    enh = "ON ✅" if user.get("enhance", True) else "OFF ❌"
    title = str(settings.get("ui_title", BOT_NAME))
    subtitle = str(settings.get("ui_subtitle", "Elite AI Image Lab • Ultra HD • Pro UI"))
    footer = str(settings.get("footer", "Rao Lab • /gen /style /model • Root Protected"))

    return (
        f"🟦 <b>{title}</b>\n"
        f"⚡ <i>{subtitle}</i>\n\n"
        f"🎨 Style : <b>{style}</b>\n"
        f"🧠 Model : <b>{model}</b>\n"
        f"✨ Enhance : <b>{enh}</b>\n\n"
        f"⚡ <b>CONTROL PANEL</b>\n"
        f"Choose Style + Model, then hit ☠️ <b>Generate</b>.\n\n"
        f"⚡ <b>COMMANDS</b>\n"
        f"/gen — Generate (private)\n"
        f"/gen PROMPT — Generate (group)\n"
        f"/style — Select style\n"
        f"/model — Select model\n"
        f"/randomstyle — Random style\n"
        f"/random PROMPT — Random style + gen\n"
        f"/enhance — Toggle enhancer\n"
        f"/tts TEXT — Text to Speech\n"
        f"/voices — List voices\n"
        f"/voice NAME — Set your voice\n"
        f"/search QUERY — Microsoft Search AI\n"
        f"/history — Last prompts\n"
        f"/current — Current settings\n"
        f"/ping — Bot status\n"
        f"/help — Help & owner\n"
        f"/id — Your chat_id\n"
        f"/uid @username — user id (only if cached)\n"
        f"/wordgame — Funny word game\n\n"
        f"☠️ {footer}"
    )
