import time
from typing import Optional
import requests
from ..config import IMAGE_API
from ..utils import build_image_url

REQUEST_TIMEOUT = 120
API_RETRIES = 2

def fetch_image_bytes(prompt: str, model: str, style_title: str) -> bytes:
    url = build_image_url(IMAGE_API, prompt, model, style_title)
    last_err: Optional[Exception] = None
    for attempt in range(API_RETRIES + 1):
        try:
            r = requests.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last_err = e
            time.sleep(1 + attempt)
    raise last_err if last_err else RuntimeError("Unknown image API error")
