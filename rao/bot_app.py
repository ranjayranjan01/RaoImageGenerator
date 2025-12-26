
import random
import io
from typing import Dict, Any, Tuple, List, Optional

import telebot
from telebot import types

from .config import BOT_TOKEN, OWNER_ID, BOT_NAME, BOT_USERNAME
from .storage import load_state, persist_state
from .utils import now_ts, today_str, human_time, trim_prompt, enhance_prompt, clean_username
from .api.image_api import fetch_image_bytes
from .api.styles_api import load_styles
from .api.tts_api import get_voices, tts_audio_bytes
from .api.search_api import search_ai
from .ui.panel import panel_text
from .ui.texts import help_text, join_required_text
from .ui.keyboards import main_kb, back_kb, gate_kb, owner_kb


class RaoBot:
    def __init__(self):
        if not BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN missing. Set Railway ENV BOT_TOKEN.")

        self.bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
        self.state = load_state()
        self.temp: Dict[str, Any] = {}
        self.owner_flow: Dict[str, Any] = {"await": None}

        # ensure required containers exist
        self.state.setdefault("users", {})
        self.state.setdefault("bans", {"banned": []})
        self.state.setdefault("styles_cache", {"styles": [], "ts": 0})
        self.state.setdefault("uname_cache", {})
        self.state.setdefault("settings", {})

        self._register_handlers()
        self._setup_commands()

    # ----------------- state helpers -----------------
    def S(self) -> dict:
        return self.state["settings"]

    def save(self):
        persist_state(self.state)

    def is_owner(self, uid: int) -> bool:
        return int(uid) == int(OWNER_ID)

    def banned(self, uid: int) -> bool:
        return str(uid) in set(map(str, self.state["bans"].get("banned", [])))

    def ban(self, uid: int):
        s = set(map(str, self.state["bans"].get("banned", [])))
        s.add(str(uid))
        self.state["bans"]["banned"] = list(s)
        self.save()

    def unban(self, uid: int):
        s = set(map(str, self.state["bans"].get("banned", [])))
        s.discard(str(uid))
        self.state["bans"]["banned"] = list(s)
        self.save()

    def cache_username(self, user):
        # Cache only if username exists
        try:
            if user and getattr(user, "username", None):
                uname = clean_username(user.username)
                self.state["uname_cache"][uname] = {
                    "id": int(user.id),
                    "name": (user.first_name or "") + ((" " + user.last_name) if user.last_name else ""),
                    "ts": now_ts()
                }
                self.save()
        except Exception:
            pass

    # ----------------- user profile -----------------
    def get_user(self, uid: int) -> dict:
        users = self.state["users"]
        k = str(uid)
        if k not in users:
            users[k] = {
                "style": str(self.S().get("default_style", "Pointillism")),
                "model": str(self.S().get("default_model", "flux")),
                "enhance": bool(self.S().get("enhance_default", True)),
                "history": [],
                "last_gen_ts": 0,
                "daily_date": "",
                "daily_used": 0,
                "game_score": 0,
                "tts_voice": "",
                "created_ts": now_ts(),
            }
            self.save()
        return users[k]

    def add_history(self, uid: int, prompt: str):
        u = self.get_user(uid)
        h = u.get("history", [])
        if not isinstance(h, list):
            h = []
        h.append(prompt)
        u["history"] = h[-12:]
        self.save()

    # ----------------- limits -----------------
    def check_daily(self, uid: int) -> Tuple[bool, str]:
        limit = int(self.S().get("daily_limit", 0))
        if limit <= 0:
            return True, ""
        u = self.get_user(uid)
        today = today_str()
        if u.get("daily_date") != today:
            u["daily_date"] = today
            u["daily_used"] = 0
            self.save()
        used = int(u.get("daily_used", 0))
        if used >= limit:
            return False, f"Daily limit reached: {used}/{limit}"
        u["daily_used"] = used + 1
        self.save()
        return True, ""

    def check_cooldown(self, uid: int) -> Tuple[bool, int]:
        cd = int(self.S().get("cooldown_seconds", 8))
        u = self.get_user(uid)
        now = now_ts()
        last = int(u.get("last_gen_ts", 0))
        wait = (last + cd) - now
        if wait > 0:
            return False, wait
        u["last_gen_ts"] = now
        self.save()
        return True, 0

    # ----------------- join gate -----------------
    def join_targets(self) -> List[dict]:
        lst = self.S().get("join_targets", [])
        out = []
        if isinstance(lst, list):
            for x in lst:
                if isinstance(x, dict) and x.get("chat"):
                    out.append({"chat": str(x["chat"]).strip(), "invite": str(x.get("invite", "")).strip()})
        return out

    def user_in_chat(self, chat: str, uid: int) -> Optional[bool]:
        try:
            m = self.bot.get_chat_member(chat, uid)
            status = getattr(m, "status", "")
            return status in ("creator", "administrator", "member")
        except Exception:
            return None

    def join_check(self, uid: int) -> Tuple[bool, List[str], List[str]]:
        if self.is_owner(uid):
            return True, [], []
        if not bool(self.S().get("join_gate_enabled", True)):
            return True, [], []
        targets = self.join_targets()
        if not targets:
            return True, [], []
        missing, unknown = [], []
        for t in targets:
            chat = t.get("chat", "").strip()
            if not chat:
                continue
            res = self.user_in_chat(chat, uid)
            if res is True:
                continue
            if res is False:
                missing.append(chat)
            if res is None:
                unknown.append(chat)

        strict = bool(self.S().get("join_gate_strict", True))
        ok = (len(missing) == 0 and (len(unknown) == 0 if strict else True))
        return ok, missing, unknown

    def ensure_access(self, chat_id: int, uid: int) -> bool:
        ok, missing, unknown = self.join_check(uid)
        if ok:
            return True
        self.bot.send_message(
            chat_id,
            join_required_text(missing, unknown),
            reply_markup=gate_kb(self.join_targets()),
            disable_web_page_preview=True
        )
        return False

    # ----------------- UI -----------------
    def send_panel(self, chat_id: int, uid: int, edit_mid: Optional[int] = None):
        u = self.get_user(uid)
        txt = panel_text(self.S(), u)
        kb = main_kb(is_owner=self.is_owner(uid), enhance_on=bool(u.get("enhance", True)))
        if edit_mid:
            self.bot.edit_message_text(txt, chat_id, edit_mid, reply_markup=kb, disable_web_page_preview=True)
        else:
            self.bot.send_message(chat_id, txt, reply_markup=kb, disable_web_page_preview=True)

    def send_owner_panel(self, chat_id: int, edit_mid: Optional[int] = None):
        txt = (
            "🧬 <b>Owner Control Room (Root)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ Manage everything from here.\n"
            "✅ Safe / stable / pro.\n"
        )
        kb = owner_kb(self.S())
        if edit_mid:
            self.bot.edit_message_text(txt, chat_id, edit_mid, reply_markup=kb, disable_web_page_preview=True)
        else:
            self.bot.send_message(chat_id, txt, reply_markup=kb, disable_web_page_preview=True)

    # ----------------- styles/models menus -----------------
    def style_menu(self, page: int = 0) -> types.InlineKeyboardMarkup:
        styles = load_styles(self.state["styles_cache"])
        self.save()
        per = 10
        total = len(styles)
        pages = max(1, (total + per - 1) // per)
        page = max(0, min(page, pages - 1))
        s = page * per
        e = min(s + per, total)

        kb = types.InlineKeyboardMarkup(row_width=2)
        for i in range(s, e):
            kb.add(types.InlineKeyboardButton(styles[i], callback_data=f"setstyle:{i}"))

        nav = []
        if page > 0:
            nav.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"stylepage:{page - 1}"))
        nav.append(types.InlineKeyboardButton(f"📄 {page + 1}/{pages}", callback_data="noop"))
        if page < pages - 1:
            nav.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"stylepage:{page + 1}"))
        kb.row(*nav)

        kb.add(types.InlineKeyboardButton("🎲 Random Style", callback_data="rand:style"))
        kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back:main"))
        return kb

    def model_menu(self) -> types.InlineKeyboardMarkup:
        models = self.S().get("models", ["flux", "sdxl"])
        if not isinstance(models, list) or not models:
            models = ["flux", "sdxl"]
        kb = types.InlineKeyboardMarkup(row_width=2)
        for m in models:
            kb.add(types.InlineKeyboardButton(str(m), callback_data=f"setmodel:{m}"))
        kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back:main"))
        return kb

    # ----------------- core actions -----------------
    def do_generate(self, chat_id: int, uid: int, prompt: str):
        """
        ✅ FIXED:
        - indentation
        - caption defined
        - BytesIO filename fix
        - proper try/except/finally
        """
        if self.banned(uid):
            self.bot.send_message(chat_id, "🚫 You are banned.")
            return

        if not self.S().get("bot_enabled", True) and not self.is_owner(uid):
            self.bot.send_message(chat_id, self.S().get("maintenance_text", "🚧 Bot OFF"))
            return

        if not self.ensure_access(chat_id, uid):
            return

        prompt = trim_prompt(prompt)
        if not prompt:
            self.bot.send_message(chat_id, "❌ Prompt missing.\nExample: <code>/gen a realistic lion in jungle</code>")
            return

        ok, msg = self.check_daily(uid)
        if not ok:
            self.bot.send_message(chat_id, f"⛔️ {msg}")
            return

        ok2, wait = self.check_cooldown(uid)
        if not ok2:
            self.bot.send_message(chat_id, f"⏳ Cooldown: wait <b>{human_time(wait)}</b>")
            return

        u = self.get_user(uid)
        style = u.get("style", self.S().get("default_style", "Pointillism"))
        model = u.get("model", self.S().get("default_model", "flux"))
        enh = bool(u.get("enhance", True))
        final_prompt = enhance_prompt(prompt) if enh else prompt

        caption = (
            f"🟦 <b>{BOT_NAME}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎨 Style: <b>{style}</b>\n"
            f"🧠 Model: <b>{model}</b>\n"
            f"✨ Enhance: <b>{'ON ✅' if enh else 'OFF ❌'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Prompt:</b> {prompt}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 {BOT_USERNAME}"
        )

        status_msg = self.bot.send_message(chat_id, f"⚡️ Generating…\n🎨 <b>{style}</b> | 🧠 <b>{model}</b>")

        try:
            img = fetch_image_bytes(final_prompt, model=model, style_title=style)

            # ✅ history save after successful fetch
            self.add_history(uid, prompt)

            photo = io.BytesIO(img)
            photo.name = "rao.png"  # ✅ IMPORTANT for Telegram API stability

            self.bot.send_photo(chat_id, photo, caption=caption)
        except Exception as e:
            try:
                self.bot.send_message(
                    chat_id,
                    "❌ Image API busy / slow hai.\n⏳ 1-2 minute baad try karo.\n\n"
                    f"Debug: <code>{e}</code>"
                )
            except Exception:
                pass
        finally:
            try:
                self.bot.delete_message(chat_id, status_msg.message_id)
            except Exception:
                pass

    def do_tts(self, chat_id: int, uid: int, text: str):
        if not self.ensure_access(chat_id, uid):
            return
        text = (text or "").strip()
        if not text:
            self.bot.send_message(chat_id, "❌ Text missing.\nExample: <code>/tts hello Rao Sahab</code>")
            return

        u = self.get_user(uid)
        voice = (u.get("tts_voice") or "").strip() or (self.S().get("tts_default_voice", "").strip())
        if not voice:
            voices = get_voices()
            voice = voices[0] if voices else "default"

        msg = self.bot.send_message(chat_id, f"🎙 Generating audio…\n<b>Voice:</b> <code>{voice}</code>")
        try:
            audio = tts_audio_bytes(text, voice)
            file = io.BytesIO(audio)
            file.name = "tts.mp3"
            self.bot.send_audio(chat_id, file, title="TTS", caption=f"🎙 <b>{voice}</b>")
            try:
                self.bot.delete_message(chat_id, msg.message_id)
            except Exception:
                pass
        except Exception as e:
            self.bot.edit_message_text(f"❌ TTS error: <code>{e}</code>", chat_id, msg.message_id)

    def do_search(self, chat_id: int, uid: int, query: str):
        if not self.ensure_access(chat_id, uid):
            return
        q = (query or "").strip()
        if not q:
            self.bot.send_message(chat_id, "❌ Query missing.\nExample: <code>/search Gaza</code>")
            return

        m = self.bot.send_message(chat_id, "🔎 Searching…")
        try:
            ans = search_ai(q)
            self.bot.edit_message_text(
                f"🔎 <b>Microsoft Search AI</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<b>Q:</b> {q}\n\n{ans}",
                chat_id, m.message_id, disable_web_page_preview=True
            )
        except Exception as e:
            self.bot.edit_message_text(f"❌ Search error: <code>{e}</code>", chat_id, m.message_id)

    # ----------------- command menu -----------------
    def _setup_commands(self):
        try:
            cmds = [
                types.BotCommand("start", "Open control panel"),
                types.BotCommand("gen", "Generate image (/gen prompt)"),
                types.BotCommand("style", "Select style"),
                types.BotCommand("model", "Select model"),
                types.BotCommand("randomstyle", "Random style"),
                types.BotCommand("random", "Random style + generate"),
                types.BotCommand("enhance", "Toggle enhancer"),
                types.BotCommand("tts", "Text to Speech"),
                types.BotCommand("voices", "List voices"),
                types.BotCommand("voice", "Set voice (/voice NAME)"),
                types.BotCommand("search", "Microsoft Search AI"),
                types.BotCommand("history", "Your history"),
                types.BotCommand("current", "Your current settings"),
                types.BotCommand("ping", "Bot status"),
                types.BotCommand("help", "Owner contact"),
                types.BotCommand("id", "Your chat_id"),
                types.BotCommand("uid", "Get user id if cached"),
                types.BotCommand("wordgame", "Funny word game"),
            ]
            self.bot.set_my_commands(cmds)
        except Exception:
            pass

    # ----------------- owner parsing -----------------
    def parse_join_line(self, text: str) -> Optional[dict]:
        """
        Accept formats:
          @channel | https://t.me/channel
          -1001234567890 | https://t.me/+InviteLink
        """
        t = (text or "").strip()
        if "|" not in t:
            return None
        left, right = [x.strip() for x in t.split("|", 1)]
        if not left or not right:
            return None
        if not (left.startswith("@") or left.startswith("-100")):
            return None
        if not (right.startswith("https://t.me/") or right.startswith("http://t.me/")):
            return None
        return {"chat": left, "invite": right}

    # ----------------- handlers -----------------
    def _register_handlers(self):
        b = self.bot

        @b.message_handler(func=lambda m: True, content_types=["text"])
        def _catch_all(m):
            # Cache username if possible
            try:
                self.cache_username(m.from_user)
            except Exception:
                pass

            uid = m.from_user.id

            # owner flow awaiting text
            if self.is_owner(uid) and self.owner_flow.get("await"):
                step = self.owner_flow["await"]
                self.owner_flow["await"] = None
                self.handle_owner_text(m, step)
                return

            return

        @b.message_handler(commands=["start"])
        def _start(m):
            uid = m.from_user.id
            if self.banned(uid):
                b.reply_to(m, "🚫 You are banned.")
                return

            ok, missing, unknown = self.join_check(uid)
            if not ok:
                b.send_message(
                    m.chat.id,
                    join_required_text(missing, unknown),
                    reply_markup=gate_kb(self.join_targets()),
                    disable_web_page_preview=True
                )
                return
            self.send_panel(m.chat.id, uid)

        @b.message_handler(commands=["help"])
        def _help(m):
            b.send_message(m.chat.id, help_text(), reply_markup=back_kb(), disable_web_page_preview=True)

        @b.message_handler(commands=["ping"])
        def _ping(m):
            b.send_message(m.chat.id, "✅ Bot is online.")

        @b.message_handler(commands=["id"])
        def _id(m):
            b.send_message(m.chat.id, f"🆔 <b>chat_id</b>: <code>{m.chat.id}</code>")

        @b.message_handler(commands=["uid"])
        def _uid(m):
            parts = m.text.split()
            if len(parts) < 2:
                b.send_message(
                    m.chat.id,
                    "Usage: <code>/uid @username</code>\n(Works only if user interacted with bot.)"
                )
                return
            uname = clean_username(parts[1])
            row = self.state["uname_cache"].get(uname)
            if not row:
                b.send_message(
                    m.chat.id,
                    f"❌ Not found in cache: <code>@{uname}</code>\nAsk user to /start the bot once."
                )
                return
            b.send_message(
                m.chat.id,
                f"✅ <b>@{uname}</b>\n🆔 <code>{row.get('id')}</code>\n👤 {row.get('name','')}".strip()
            )

        @b.message_handler(commands=["gen"])
        def _gen(m):
            uid = m.from_user.id
            prompt = m.text.split(" ", 1)[1] if " " in m.text else ""

            if m.chat.type != "private" and not prompt:
                b.reply_to(m, "❌ Group me: <code>/gen your prompt</code>")
                return
            if m.chat.type == "private" and not prompt:
                b.reply_to(m, "✍️ Send prompt like: <code>/gen a realistic tiger in neon city</code>")
                return

            self.do_generate(m.chat.id, uid, prompt)

        @b.message_handler(commands=["style"])
        def _style(m):
            uid = m.from_user.id
            if not self.ensure_access(m.chat.id, uid):
                return
            b.send_message(m.chat.id, "🎨 <b>Select Style</b>", reply_markup=self.style_menu(0))

        @b.message_handler(commands=["model"])
        def _model(m):
            uid = m.from_user.id
            if not self.ensure_access(m.chat.id, uid):
                return
            b.send_message(m.chat.id, "🧠 <b>Select Model</b>", reply_markup=self.model_menu())

        @b.message_handler(commands=["randomstyle"])
        def _rs(m):
            uid = m.from_user.id
            if not self.ensure_access(m.chat.id, uid):
                return
            styles = load_styles(self.state["styles_cache"])
            self.save()
            u = self.get_user(uid)
            u["style"] = random.choice(styles)
            self.save()
            self.send_panel(m.chat.id, uid)

        @b.message_handler(commands=["random"])
        def _random(m):
            uid = m.from_user.id
            prompt = m.text.split(" ", 1)[1] if " " in m.text else ""
            if not prompt:
                b.send_message(m.chat.id, "Usage: <code>/random your prompt</code>")
                return
            styles = load_styles(self.state["styles_cache"])
            self.save()
            u = self.get_user(uid)
            u["style"] = random.choice(styles)
            self.save()
            self.do_generate(m.chat.id, uid, prompt)

        @b.message_handler(commands=["enhance"])
        def _enh(m):
            uid = m.from_user.id
            u = self.get_user(uid)
            u["enhance"] = not bool(u.get("enhance", True))
            self.save()
            self.send_panel(m.chat.id, uid)

        @b.message_handler(commands=["history"])
        def _hist(m):
            uid = m.from_user.id
            u = self.get_user(uid)
            h = u.get("history", [])
            if not h:
                b.send_message(m.chat.id, "📜 No history yet.")
                return
            out = "📜 <b>Your last prompts</b>\n━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join([f"• {x}" for x in h[::-1]])
            b.send_message(m.chat.id, out)

        @b.message_handler(commands=["current"])
        def _cur(m):
            uid = m.from_user.id
            u = self.get_user(uid)
            b.send_message(
                m.chat.id,
                "📌 <b>Current</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎨 <b>{u.get('style')}</b>\n"
                f"🧠 <b>{u.get('model')}</b>\n"
                f"✨ <b>{'ON ✅' if u.get('enhance') else 'OFF ❌'}</b>"
            )

        @b.message_handler(commands=["tts"])
        def _tts(m):
            uid = m.from_user.id
            t = m.text.split(" ", 1)[1] if " " in m.text else ""
            self.do_tts(m.chat.id, uid, t)

        @b.message_handler(commands=["voices"])
        def _voices(m):
            if not self.ensure_access(m.chat.id, m.from_user.id):
                return
            try:
                voices = get_voices()
                if not voices:
                    b.send_message(m.chat.id, "❌ No voices returned by API.")
                    return
                show = voices[:80]
                b.send_message(
                    m.chat.id,
                    "🎙 <b>Available Voices</b>\n━━━━━━━━━━━━━━━━━━━━━━\n" +
                    "\n".join([f"• <code>{v}</code>" for v in show])
                )
            except Exception as e:
                b.send_message(m.chat.id, f"❌ Error: <code>{e}</code>")

        @b.message_handler(commands=["voice"])
        def _voice(m):
            uid = m.from_user.id
            if not self.ensure_access(m.chat.id, uid):
                return
            name = m.text.split(" ", 1)[1].strip() if " " in m.text else ""
            if not name:
                b.send_message(m.chat.id, "Usage: <code>/voice VoiceName</code>\nUse /voices to list.")
                return
            u = self.get_user(uid)
            u["tts_voice"] = name
            self.save()
            b.send_message(m.chat.id, f"✅ Your voice set to: <code>{name}</code>")

        @b.message_handler(commands=["search"])
        def _search(m):
            uid = m.from_user.id
            q = m.text.split(" ", 1)[1] if " " in m.text else ""
            self.do_search(m.chat.id, uid, q)

        @b.message_handler(commands=["wordgame"])
        def _wg(m):
            uid = m.from_user.id
            self.start_game(m.chat.id, uid)

        # ---------------- Callback buttons ----------------
        @b.callback_query_handler(func=lambda c: True)
        def _cb(c):
            uid = c.from_user.id
            data = c.data or ""

            try:
                if data == "noop":
                    b.answer_callback_query(c.id)
                    return

                if data == "back:main":
                    self.send_panel(c.message.chat.id, uid, edit_mid=c.message.message_id)
                    b.answer_callback_query(c.id)
                    return

                if data == "menu:help":
                    b.edit_message_text(
                        help_text(), c.message.chat.id, c.message.message_id,
                        reply_markup=back_kb(), disable_web_page_preview=True
                    )
                    b.answer_callback_query(c.id)
                    return

                if data == "menu:history":
                    u = self.get_user(uid)
                    h = u.get("history", [])
                    txt = "📜 <b>Your last prompts</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    txt += "\n".join([f"• {x}" for x in h[::-1]]) if h else "No history yet."
                    b.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                                        reply_markup=back_kb(), disable_web_page_preview=True)
                    b.answer_callback_query(c.id)
                    return

                if data == "menu:current":
                    u = self.get_user(uid)
                    txt = (
                        "📌 <b>Current</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🎨 <b>{u.get('style')}</b>\n"
                        f"🧠 <b>{u.get('model')}</b>\n"
                        f"✨ <b>{'ON ✅' if u.get('enhance') else 'OFF ❌'}</b>"
                    )
                    b.edit_message_text(txt, c.message.chat.id, c.message.message_id,
                                        reply_markup=back_kb(), disable_web_page_preview=True)
                    b.answer_callback_query(c.id)
                    return

                if data == "toggle:enhance":
                    u = self.get_user(uid)
                    u["enhance"] = not bool(u.get("enhance", True))
                    self.save()
                    self.send_panel(c.message.chat.id, uid, edit_mid=c.message.message_id)
                    b.answer_callback_query(c.id, "Updated")
                    return

                if data == "menu:style":
                    if not self.ensure_access(c.message.chat.id, uid):
                        b.answer_callback_query(c.id)
                        return
                    b.edit_message_text(
                        "🎨 <b>Select Style</b>", c.message.chat.id, c.message.message_id,
                        reply_markup=self.style_menu(0), disable_web_page_preview=True
                    )
                    b.answer_callback_query(c.id)
                    return

                if data.startswith("stylepage:"):
                    page = int(data.split(":", 1)[1])
                    b.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=self.style_menu(page))
                    b.answer_callback_query(c.id)
                    return

                if data.startswith("setstyle:"):
                    idx = int(data.split(":", 1)[1])
                    styles = load_styles(self.state["styles_cache"])
                    self.save()
                    if 0 <= idx < len(styles):
                        u = self.get_user(uid)
                        u["style"] = styles[idx]
                        self.save()
                    self.send_panel(c.message.chat.id, uid, edit_mid=c.message.message_id)
                    b.answer_callback_query(c.id, "Style updated")
                    return

                if data == "rand:style":
                    styles = load_styles(self.state["styles_cache"])
                    self.save()
                    u = self.get_user(uid)
                    u["style"] = random.choice(styles)
                    self.save()
                    self.send_panel(c.message.chat.id, uid, edit_mid=c.message.message_id)
                    b.answer_callback_query(c.id, "Random style set")
                    return

                if data == "menu:model":
                    if not self.ensure_access(c.message.chat.id, uid):
                        b.answer_callback_query(c.id)
                        return
                    b.edit_message_text(
                        "🧠 <b>Select Model</b>", c.message.chat.id, c.message.message_id,
                        reply_markup=self.model_menu(), disable_web_page_preview=True
                    )
                    b.answer_callback_query(c.id)
                    return

                if data.startswith("setmodel:"):
                    model = data.split(":", 1)[1]
                    u = self.get_user(uid)
                    u["model"] = model
                    self.save()
                    self.send_panel(c.message.chat.id, uid, edit_mid=c.message.message_id)
                    b.answer_callback_query(c.id, "Model updated")
                    return

                if data == "gen:ask":
                    b.answer_callback_query(c.id)
                    b.send_message(c.message.chat.id, "✍️ Send: <code>/gen your prompt</code>")
                    return

                if data == "gate:recheck":
                    ok, missing, unknown = self.join_check(uid)
                    if ok:
                        b.answer_callback_query(c.id, "✅ Verified! Now /start again")
                        b.edit_message_text(
                            "✅ Verified! Ab <b>/start</b> dubara bhejo.",
                            c.message.chat.id, c.message.message_id,
                            disable_web_page_preview=True
                        )
                    else:
                        b.answer_callback_query(c.id, "❌ Not joined yet")
                        b.edit_message_text(
                            join_required_text(missing, unknown),
                            c.message.chat.id, c.message.message_id,
                            reply_markup=gate_kb(self.join_targets()),
                            disable_web_page_preview=True
                        )
                    return

                # Game callbacks
                if data == "game:start":
                    b.answer_callback_query(c.id)
                    self.start_game(c.message.chat.id, uid)
                    return
                if data == "game:show":
                    b.answer_callback_query(c.id)
                    st = self.temp.get(str(uid), {})
                    b.send_message(c.message.chat.id, f"😂 Meaning: <b>{st.get('meaning', 'No game')}</b>")
                    return

                # Owner panel
                if data.startswith("owner:"):
                    b.answer_callback_query(c.id)
                    if not self.is_owner(uid):
                        b.send_message(c.message.chat.id, "⛔️ Root only.")
                        return
                    self.handle_owner_callback(c, data)
                    return

                b.answer_callback_query(c.id)
            except Exception:
                try:
                    b.answer_callback_query(c.id)
                except Exception:
                    pass

    # ----------------- word game -----------------
    def start_game(self, chat_id: int, uid: int):
        word, meaning = random.choice([
            ("Jugadu", "Smart solution nikalne wala 😄"),
            ("Bakchod", "Masti + talks mode ON 🤣"),
            ("Funda", "Idea / concept 💡"),
            ("Khatarnak", "Super dangerous but cool 😎"),
            ("Mast", "Very good / awesome 🔥"),
        ])
        self.temp[str(uid)] = {"word": word, "meaning": meaning}
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("👀 Show Meaning", callback_data="game:show"))
        kb.add(types.InlineKeyboardButton("🔁 New Word", callback_data="game:start"))
        kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back:main"))
        self.bot.send_message(
            chat_id,
            f"🎮 <b>Funny Word Game</b>\n━━━━━━━━━━━━━━━━━━━━━━\nGuess meaning of: <b>{word}</b>",
            reply_markup=kb
        )

    # ----------------- owner handlers -----------------
    def handle_owner_callback(self, c, data: str):
        chat_id = c.message.chat.id
        mid = c.message.message_id

        if data == "owner:panel":
            self.send_owner_panel(chat_id, edit_mid=mid)
            return

        if data == "owner:toggle_bot":
            self.S()["bot_enabled"] = not bool(self.S().get("bot_enabled", True))
            self.save()
            self.send_owner_panel(chat_id, edit_mid=mid)
            return

        if data == "owner:set_cooldown":
            self.owner_flow["await"] = "cooldown"
            self.bot.send_message(chat_id, "⏱️ Send cooldown seconds (example: <code>8</code>)")
            return

        if data == "owner:set_daily":
            self.owner_flow["await"] = "daily"
            self.bot.send_message(chat_id, "📅 Send daily limit (0=unlimited). Example: <code>40</code>")
            return

        if data == "owner:toggle_gate":
            self.S()["join_gate_enabled"] = not bool(self.S().get("join_gate_enabled", True))
            self.save()
            self.send_owner_panel(chat_id, edit_mid=mid)
            return

        if data == "owner:toggle_strict":
            self.S()["join_gate_strict"] = not bool(self.S().get("join_gate_strict", True))
            self.save()
            self.send_owner_panel(chat_id, edit_mid=mid)
            return

        if data == "owner:add_join":
            self.owner_flow["await"] = "add_join"
            self.bot.send_message(
                chat_id,
                "➕ <b>Add Join Target</b>\n"
                "Send like:\n"
                "<code>@channel_username | https://t.me/channel_username</code>\n\n"
                "OR private:\n"
                "<code>-1001234567890 | https://t.me/+InviteLink</code>",
                disable_web_page_preview=True
            )
            return

        if data == "owner:remove_join":
            self.owner_flow["await"] = "remove_join"
            self.bot.send_message(chat_id, "➖ Send chat to remove (example: <code>@channel</code> OR <code>-100...</code>)")
            return

        if data == "owner:list_join":
            targets = self.join_targets()
            if not targets:
                self.bot.send_message(chat_id, "📋 No join targets set.")
                return
            txt = "📋 <b>Join Targets</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
            for i, t in enumerate(targets, 1):
                txt += f"{i}) <code>{t['chat']}</code>\n   🔗 {t.get('invite','')}\n"
            self.bot.send_message(chat_id, txt, disable_web_page_preview=True)
            return

        if data == "owner:models":
            self.owner_flow["await"] = "models"
            self.bot.send_message(chat_id, "🧠 Send models list comma-separated.\nExample: <code>flux, sdxl</code>")
            return

        if data == "owner:ui_text":
            self.owner_flow["await"] = "ui_text"
            self.bot.send_message(chat_id, "📝 Send UI text like:\n<code>Title | Subtitle | Footer</code>")
            return

        if data == "owner:refresh_styles":
            self.state["styles_cache"]["styles"] = []
            self.state["styles_cache"]["ts"] = 0
            self.save()
            self.bot.send_message(chat_id, "✅ Styles cache cleared. Next style menu will refetch.")
            return

        if data == "owner:stats":
            users = self.state["users"]
            bans = self.state["bans"].get("banned", [])
            txt = (
                "📊 <b>Stats</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 Users: <b>{len(users)}</b>\n"
                f"🚫 Banned: <b>{len(bans)}</b>\n"
                f"🤖 Bot: <b>{'ON' if self.S().get('bot_enabled', True) else 'OFF'}</b>\n"
                f"🔒 Gate: <b>{'ON' if self.S().get('join_gate_enabled', True) else 'OFF'}</b>\n"
            )
            self.bot.send_message(chat_id, txt)
            return

        if data == "owner:broadcast":
            self.owner_flow["await"] = "broadcast"
            self.bot.send_message(chat_id, "📢 Send broadcast message text (it will go to all users).")
            return

        if data == "owner:ban_unban":
            self.owner_flow["await"] = "ban_unban"
            self.bot.send_message(chat_id, "🚫 Send: <code>ban 123</code> or <code>unban 123</code>")
            return

        if data == "owner:reset_user":
            self.owner_flow["await"] = "reset_user"
            self.bot.send_message(chat_id, "♻️ Send user id to reset.\nExample: <code>7702984107</code>")
            return

        if data == "owner:reset_all":
            self.state["users"] = {}
            self.save()
            self.bot.send_message(chat_id, "🧨 Reset ALL users done.")
            return

    def handle_owner_text(self, m, step: str):
        chat_id = m.chat.id
        text = (m.text or "").strip()

        if step == "cooldown":
            try:
                self.S()["cooldown_seconds"] = max(0, int(text))
                self.save()
                self.bot.send_message(chat_id, "✅ Cooldown updated.")
            except Exception:
                self.bot.send_message(chat_id, "❌ Invalid number.")
            return

        if step == "daily":
            try:
                self.S()["daily_limit"] = max(0, int(text))
                self.save()
                self.bot.send_message(chat_id, "✅ Daily limit updated.")
            except Exception:
                self.bot.send_message(chat_id, "❌ Invalid number.")
            return

        if step == "add_join":
            obj = self.parse_join_line(text)
            if not obj:
                self.bot.send_message(
                    chat_id,
                    "❌ Format wrong.\nUse:\n<code>@channel | https://t.me/channel</code>\nOR\n<code>-100... | https://t.me/+InviteLink</code>"
                )
                return
            targets = self.join_targets()
            chats = set([t["chat"] for t in targets])
            if obj["chat"] in chats:
                self.bot.send_message(chat_id, "⚠️ Already added.")
                return
            targets.append(obj)
            self.S()["join_targets"] = targets
            self.save()
            self.bot.send_message(chat_id, f"✅ Added join target: <code>{obj['chat']}</code>")
            return

        if step == "remove_join":
            targets = self.join_targets()
            before = len(targets)
            targets = [t for t in targets if t.get("chat") != text]
            self.S()["join_targets"] = targets
            self.save()
            if len(targets) == before:
                self.bot.send_message(chat_id, "❌ Not found.")
            else:
                self.bot.send_message(chat_id, "✅ Removed.")
            return

        if step == "models":
            parts = [p.strip() for p in text.split(",") if p.strip()]
            if not parts:
                self.bot.send_message(chat_id, "❌ Empty.")
                return
            self.S()["models"] = parts
            self.save()
            self.bot.send_message(chat_id, "✅ Models updated.")
            return

        if step == "ui_text":
            if text.count("|") < 2:
                self.bot.send_message(chat_id, "❌ Use: <code>Title | Subtitle | Footer</code>")
                return
            a, b, c = [x.strip() for x in text.split("|", 2)]
            self.S()["ui_title"] = a
            self.S()["ui_subtitle"] = b
            self.S()["footer"] = c
            self.save()
            self.bot.send_message(chat_id, "✅ UI text updated.")
            return

        if step == "broadcast":
            sent = 0
            for uid_str in list(self.state["users"].keys()):
                try:
                    self.bot.send_message(int(uid_str), f"📢 <b>Broadcast</b>\n━━━━━━━━━━━━━━━━━━━━━━\n{text}")
                    sent += 1
                except Exception:
                    pass
            self.bot.send_message(chat_id, f"✅ Broadcast sent to: <b>{sent}</b> users.")
            return

        if step == "ban_unban":
            parts = text.split()
            if len(parts) != 2:
                self.bot.send_message(chat_id, "❌ Use: <code>ban 123</code> or <code>unban 123</code>")
                return
            cmd, uid_s = parts[0].lower(), parts[1]
            try:
                uid = int(uid_s)
            except Exception:
                self.bot.send_message(chat_id, "❌ Invalid ID.")
                return
            if cmd == "ban":
                self.ban(uid)
                self.bot.send_message(chat_id, f"✅ Banned: <code>{uid}</code>")
            elif cmd == "unban":
                self.unban(uid)
                self.bot.send_message(chat_id, f"✅ Unbanned: <code>{uid}</code>")
            else:
                self.bot.send_message(chat_id, "❌ Use ban/unban.")
            return

        if step == "reset_user":
            try:
                uid = int(text)
            except Exception:
                self.bot.send_message(chat_id, "❌ Invalid user id.")
                return
            self.state["users"].pop(str(uid), None)
            self.save()
            self.bot.send_message(chat_id, f"✅ Reset done for: <code>{uid}</code>")
            return

    # ----------------- run -----------------
    def run(self):
    print("✅ RaoBot polling started")
    try:
        self.bot.remove_webhook(drop_pending_updates=True)
    except Exception:
        pass

    # thread=False => conflict chances kam
    self.bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True, none_stop=True)
