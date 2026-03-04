from __future__ import annotations
import json
import re
import time
from functools import lru_cache
from typing import Any
from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from config.settings import settings
from utils.logger import get_logger
logger = get_logger(__name__)
import threading

class ClientState:
    def __init__(self):
        self.last_key_index = 0
        self.lock = threading.Lock()

_state = ClientState()

def _get_api_keys() -> list[str]:
    keys = [settings.gemini_api_key]
    if settings.google_api_key:
        keys.append(settings.google_api_key)
    return keys

def _get_next_client() -> genai.Client:
    keys = _get_api_keys()
    with _state.lock:
        key = keys[_state.last_key_index % len(keys)]
        _state.last_key_index += 1
    return genai.Client(api_key=key)

@retry(
    retry=retry_if_exception_type(Exception),
    # Wait longer if we hit quota (429) - tenacity wait_exponential
    wait=wait_exponential(multiplier=2, min=5, max=60), 
    stop=stop_after_attempt(5),
    reraise=True,
)
def generate_text(
    prompt: str,
    temperature: float | None = None,
    max_tokens: int = 4096,
    response_mime_type: str | None = None,
) -> str:
    client = _get_next_client()

    config = types.GenerateContentConfig(
        temperature=temperature if temperature is not None else 0.1,
        top_p=0.95,
        max_output_tokens=max_tokens,
        response_mime_type=response_mime_type,
    )

    start = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=config,
        )
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            logger.warning("Quota reached (429). Waiting before retry... Error: %s", e)
            time.sleep(10) 
        raise e

    elapsed = time.perf_counter() - start

    text = response.text.strip()
    logger.debug("Gemini response (%.2fs): %s.........", elapsed, text[:40].replace("\n", " "))
    return text

def generate_json(prompt: str, temperature: float = 0.1) -> dict[str, Any]:
    raw = generate_text(prompt, temperature=temperature, response_mime_type="application/json")

    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed. Raw response:\n%s", raw)
        raise ValueError(f"Gemini did not return valid JSON: {e}") from e

def generate_with_high_creativity(prompt: str) -> str:
    return generate_text(prompt, temperature=0.7, max_tokens=1024)
