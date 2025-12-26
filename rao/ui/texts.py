from ..config import OWNER_NAME, OWNER_USERNAME, OWNER_LINK, OWNER_BIO

def help_text() -> str:
    return (
        "ℹ️ <b>Help & Support</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Owner:</b> {OWNER_NAME}\n"
        f"🔗 <b>Username:</b> {OWNER_USERNAME}\n"
        f"🌐 <b>Link:</b> <a href=\"{OWNER_LINK}\">{OWNER_LINK}</a>\n"
        f"📝 <b>Bio:</b> {OWNER_BIO}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Image:</b> /gen prompt\n"
        "🎙 <b>TTS:</b> /tts text\n"
        "🔎 <b>Search:</b> /search query\n"
    )

def join_required_text(missing: list, unknown: list) -> str:
    msg = "🔒 <b>Join Required</b>\n\n"
    msg += "पहले नीचे वाले group/channel को join करो, उसके बाद ही bot use कर पाओगे ✅\n\n"
    if missing:
        msg += "❌ <b>Missing Join:</b>\n" + "\n".join([f"• <code>{x}</code>" for x in missing]) + "\n\n"
    if unknown:
        msg += "⚠️ <b>Verify not possible:</b>\n" + "\n".join([f"• <code>{x}</code>" for x in unknown]) + "\n\n"
        msg += "👉 Private group/channel verify ke liye bot ko admin/member banao.\n\n"
    msg += "✅ Join karne ke baad <b>I Joined (Recheck)</b> dabao.\n"
    msg += "✅ Verified ho jaaye to <b>/start</b> dobara bhejo."
    return msg
