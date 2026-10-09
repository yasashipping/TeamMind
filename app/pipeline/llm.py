"""
app/pipeline/llm.py — Claude (Anthropic) istemcisi.

SDK gerektirmez; ham HTTPS uzerinden Messages API cagrir.
Guvenlik: anahtar .env / ortam degiskeninden gelir, koda yazilmaz.
Dayaniklilik: JSON dogrulamasi basarisizsa 1 kez "tamir" cagrisi yapilir.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

from app.core.config import settings
from app.schemas.analysis import (
    SegmentationResult, ExtractionResult, QualityResult)

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


class LLMError(RuntimeError):
    pass


def _load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, name), encoding="utf-8") as f:
        return f.read()


def _extract_json(text: str) -> dict:
    """LLM cevabindan JSON ayikla (```json kulubezi dahil)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise LLMError(f"LLM ciktisinda JSON bulunamadi: {text[:200]}")
    return json.loads(m.group(0))


def _call(messages: list[dict]) -> str:
    if not settings.llm_api_key:
        raise LLMError("ANTHROPIC_API_KEY tanimli degil — .env dosyasina ekleyin")
    # Not: yeni modellerde 'temperature' deprecated -> gondermiyoruz.
    # Deterministiklik, prompt'taki katı kurallar + tamir dongusuyle saglanir.
    body = json.dumps({
        "model": settings.llm_model,
        "max_tokens": 4096,
        "messages": messages,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body, method="POST", headers={
            "x-api-key": settings.llm_api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        })
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise LLMError(f"Anthropic API hatasi {e.code}: {e.read()[:300]}") from e
    return "".join(b.get("text", "") for b in payload.get("content", []))


def _call_validated(system_prompt: str, user_content: str, response_model):
    """Cagri + Pydantic dogrulama; hata durumunda tek tamir cagrisi."""
    last_err = None
    for attempt in range(settings.llm_max_retries + 1):
        try:
            raw = _call([{"role": "user",
                          "content": system_prompt + "\n\n" + user_content}])
            return response_model.model_validate(_extract_json(raw))
        except Exception as e:                     # JSON hatasi / schema hatasi
            last_err = e
            if attempt == 0:
                repair = (
                    "Önceki çıktın geçerli JSON değildi veya şemaya uymadı: "
                    f"{e}\nŞemaya tam uyumlu, sadece JSON döndür.")
                system_prompt += "\n\n[REPAIR] " + repair
    raise LLMError(f"LLM dogrulamasi {settings.llm_max_retries + 1} denemede basarisiz: {last_err}")


def segment(numbered_transcript: str) -> SegmentationResult:
    p = _load_prompt("segmentation.txt").format(transcript=numbered_transcript)
    return _call_validated(p, "", SegmentationResult)


def extract(topic_title: str, segment_text: str,
            start: int | None = None, end: int | None = None,
            meeting_date: str | None = None) -> ExtractionResult:
    p = _load_prompt("extraction.txt").format(
        topic_title=topic_title, start=start or "?", end=end or "?",
        meeting_date=meeting_date or "bilinmiyor",
        segment_text=segment_text)
    return _call_validated(p, "", ExtractionResult)


def filter_and_summarize(items_json: str) -> QualityResult:
    p = _load_prompt("quality.txt").format(items_json=items_json)
    return _call_validated(p, "", QualityResult)
