from telebot import types

def main_kb(is_owner: bool, enhance_on: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎨 Styles", callback_data="menu:style"),
        types.InlineKeyboardButton("🧠 Models", callback_data="menu:model"),
    )
    kb.add(
        types.InlineKeyboardButton("☠️ Generate", callback_data="gen:ask"),
        types.InlineKeyboardButton("📜 History", callback_data="menu:history"),
    )
    kb.add(
        types.InlineKeyboardButton(f"✨ Enhance: {'✅ ON' if enhance_on else '❌ OFF'}", callback_data="toggle:enhance"),
        types.InlineKeyboardButton("🎮 Word Game", callback_data="game:start"),
    )
    kb.add(
        types.InlineKeyboardButton("🎙 TTS", callback_data="tts:ask"),
        types.InlineKeyboardButton("🔎 Search AI", callback_data="search:ask"),
    )
    kb.add(
        types.InlineKeyboardButton("ℹ️ Help", callback_data="menu:help"),
        types.InlineKeyboardButton("📌 Current", callback_data="menu:current"),
    )
    if is_owner:
        kb.add(types.InlineKeyboardButton("🧬 Owner Control Room (Root)", callback_data="owner:panel"))
    return kb

def back_kb() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back:main"))
    return kb

def gate_kb(targets: list) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for t in targets[:10]:
        chat = t.get("chat","")
        inv = t.get("invite","")
        if inv:
            kb.add(types.InlineKeyboardButton(f"✅ Join {chat}", url=inv))
    kb.add(types.InlineKeyboardButton("🔄 I Joined (Recheck)", callback_data="gate:recheck"))
    kb.add(types.InlineKeyboardButton("ℹ️ Help", callback_data="menu:help"))
    return kb

def owner_kb(settings: dict) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(f"🤖 Bot: {'✅ ON' if settings.get('bot_enabled', True) else '❌ OFF'}", callback_data="owner:toggle_bot"),
        types.InlineKeyboardButton("⏱ Cooldown", callback_data="owner:set_cooldown"),
    )
    kb.add(
        types.InlineKeyboardButton("📅 Daily Limit", callback_data="owner:set_daily"),
        types.InlineKeyboardButton("📊 Stats", callback_data="owner:stats"),
    )
    kb.add(
        types.InlineKeyboardButton(f"🔒 Gate: {'✅ ON' if settings.get('join_gate_enabled', True) else '❌ OFF'}", callback_data="owner:toggle_gate"),
        types.InlineKeyboardButton(f"🛡 Strict: {'✅' if settings.get('join_gate_strict', True) else '❌'}", callback_data="owner:toggle_strict"),
    )
    kb.add(
        types.InlineKeyboardButton("➕ Add Join", callback_data="owner:add_join"),
        types.InlineKeyboardButton("➖ Remove Join", callback_data="owner:remove_join"),
    )
    kb.add(
        types.InlineKeyboardButton("📋 List Joins", callback_data="owner:list_join"),
        types.InlineKeyboardButton("🧠 Models", callback_data="owner:models"),
    )
    kb.add(
        types.InlineKeyboardButton("🎨 Defaults", callback_data="owner:defaults"),
        types.InlineKeyboardButton("📝 UI Text", callback_data="owner:ui_text"),
    )
    kb.add(
        types.InlineKeyboardButton("🎙 TTS Voice", callback_data="owner:set_tts_voice"),
        types.InlineKeyboardButton("🔄 Refresh Styles", callback_data="owner:refresh_styles"),
    )
    kb.add(
        types.InlineKeyboardButton("📢 Broadcast", callback_data="owner:broadcast"),
        types.InlineKeyboardButton("🚫 Ban/Unban", callback_data="owner:ban_unban"),
    )
    kb.add(
        types.InlineKeyboardButton("♻️ Reset User", callback_data="owner:reset_user"),
        types.InlineKeyboardButton("🧨 Reset ALL", callback_data="owner:reset_all"),
    )
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back:main"))
    return kb
