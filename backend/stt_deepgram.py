"""stt_deepgram.py — Deepgram Nova ile Turkce transkript (konusmaci ayrimi dahil).

GoogleSTTEngine ile ayni arayuz: transcribe(path) -> [Line(start_sec, text, speaker)]
Uzun dosyalar: Deepgram pre-recorded API tek istekte 2 GB'a kadar kabul eder, bucket gerekmez.

Env:
  DEEPGRAM_API_KEY
  STT_DIARIZE=1   (konusmaci etiketleri K1, K2 ...)
"""
import os
from dataclasses import dataclass

import httpx


@dataclass
class Line:
    start_sec: float
    text: str
    speaker: str | None = None


class DeepgramSTTEngine:
    URL = "https://api.deepgram.com/v1/listen"

    def __init__(self, api_key: str | None = None, model: str = "nova-3",
                 language: str = "tr", diarize: bool = False):
        self.api_key = api_key or os.environ["DEEPGRAM_API_KEY"]
        self.model, self.language, self.diarize = model, language, diarize

    def transcribe(self, path: str, timeout_sec: int = 3600) -> list[Line]:
        params = {
            "model": self.model,
            "language": self.language,
            "smart_format": "true",
            "punctuate": "true",
            "utterances": "true",
            "diarize": "true" if self.diarize else "false",
        }
        with open(path, "rb") as f:
            data = f.read()
        r = httpx.post(self.URL, params=params, content=data,
                       headers={"Authorization": f"Token {self.api_key}",
                                "Content-Type": "audio/mp4"},
                       timeout=timeout_sec)
        r.raise_for_status()
        j = r.json()

        lines: list[Line] = []
        for u in j.get("results", {}).get("utterances", []):
            text = (u.get("transcript") or "").strip()
            if not text:
                continue
            spk = f"K{u['speaker'] + 1}" if self.diarize and "speaker" in u else None
            lines.append(Line(float(u["start"]), text, spk))

        if not lines:
            alt = j["results"]["channels"][0]["alternatives"][0]
            if alt.get("transcript"):
                lines.append(Line(0.0, alt["transcript"].strip()))
        return lines


def to_numbered_transcript(lines: list[Line]) -> str:
    out = []
    for i, l in enumerate(lines):
        spk = f" | {l.speaker}" if l.speaker else ""
        out.append(f"{i} | {l.start_sec:7.1f}s{spk} | {l.text}")
    return "\n".join(out)


def to_llm_transcript(lines: list[Line]) -> str:
    return "\n".join(
        f"{i} | {l.speaker} | {l.text}" if l.speaker else f"{i} | {l.text}"
        for i, l in enumerate(lines))
