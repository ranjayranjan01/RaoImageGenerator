import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

BOT_NAME = os.getenv("BOT_NAME", "˹𝐑𝐀𝐎 𝐈𝐌𝐀𝐆𝐄 𝐆𝐄𝐍𝐄𝐑𝐀𝐓𝐎𝐑˼ ༄").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "@RaoImagery_bot").strip()

OWNER_ID = int(os.getenv("OWNER_ID", "7702984107").strip() or "7702984107")
OWNER_NAME = os.getenv("OWNER_NAME", "𝐑𝐚𝐨 𝐒𝐚𝐡𝐚𝐛 𝐉𝐢𝐢 ❣️").strip()
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "@RaoSahab_Ji01").strip()
OWNER_LINK = os.getenv("OWNER_LINK", "https://t.me/RaoSahab_Ji01").strip()
OWNER_BIO = os.getenv("OWNER_BIO", "हरि हराये नमः कृष्ण यादवाय नमः , यादवाय माधवाय केशवाय नमः।।").strip()

# APIs
IMAGE_API = "https://text2img.hideme.eu.org/image"
STYLES_API = "https://text2img.hideme.eu.org/image?style=all"

TTS_API = "https://yabes-api.pages.dev/api/tools/tts"
MS_SEARCH_AI = "https://bj-microsoft-search-ai.vercel.app/"

DATA_DIR = os.getenv("DATA_DIR", ".data").strip()
