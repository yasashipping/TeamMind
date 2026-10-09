"""
app/pipeline/live.py — Canli dinleme cekirdegi (Modul 4).

Ses altyapisi (LiveKit/WebRTC) bu modulun DISINDADIR; burada test
edilebilir iki algoritma var:

1) RollingAssembler: STT'in 30 sn'lik chunk'larindan (bazi yarim kalmis)
   tekil, tekrarsiz bir transkript akisi uretir.
   - Chunk sinirinda kopan cumleler sonraki chunk ile birlestirilir.
   - Ust uste binen kisim (overlap) cikarilir; tekrar yazilmaz.

2) SignalDetector: TAMAMLANMIS cumlelerde karar/aksiyon sinyalleri
   arar; bulunca anlik bir "olay" yayar. LLM her cumlede cagrilmaz —
   sadece sinyal tetiklerinde (maliyet ~10x duser).

Canli mod uretilen olaylar TASLAKTIR; toplantinin final raporu her
zaman toplanti-sonrasi standart pipeline'dan (tasks.py) gelir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ChunkResult:
    """Bir chunk'in STT ciktisi."""
    text: str
    is_final: bool = False   # chunk kapanirken endpoint algilandi mi
    chunk_no: int = 0


class RollingAssembler:
    """Chunk'lari birlestirip cumle bazli akis uretir."""

    def __init__(self, overlap_window: int = 80):
        self.buffer = ""
        self.overlap_window = overlap_window
        self._last_chunk_tail = ""

    def _strip_overlap(self, new_text: str) -> str:
        """Yeni chunk'in basi, onceki chunk'in sonuyla ortusuyorsa
        ortusen kismi at. Uzunluk tabanli pencere + suffix/prefix
        eslesmesi; maliyeti dusuk ve deterministik."""
        tail = self._last_chunk_tail
        max_ov = min(len(tail), len(new_text), self.overlap_window)
        for ov in range(max_ov, 3, -1):
            if tail[-ov:] == new_text[:ov]:
                return new_text[ov:]
        return new_text

    def feed(self, chunk: ChunkResult) -> list[str]:
        """Yeni chunk'i isle; TAMAMLANAN cumleleri dondur.

        is_final=False chunk'larda son cumle henuz kapanmamis olabilir;
        buffer'da tutulur, bir sonraki chunk ile birlestirilir.
        is_final=True oldugunda kalan tum cumleler kapatilir.
        """
        text = self._strip_overlap(chunk.text)
        merged = (self.buffer + " " + text).strip()
        self.buffer = re.sub(r"\s+", " ", merged)   # overlap birlesme boslugu
        self._last_chunk_tail = text[-self.overlap_window:]

        # cumle sonu: . ! ? ya da is_final
        sentences = re.split(r"(?<=[.!?])\s+", self.buffer)
        if chunk.is_final:
            complete, self.buffer = sentences, ""
        else:
            # son parca henuz kapanmamis cumle -> buffer'da kalsin
            if sentences and not re.search(r"[.!?]\s*$", self.buffer):
                complete, self.buffer = sentences[:-1], sentences[-1]
            else:
                complete, self.buffer = sentences, ""
        return [s.strip() for s in complete if s.strip()]


# ---------------------------------------------------------------- sinyaller

@dataclass
class LiveEvent:
    kind: str            # 'decision' | 'action'
    text: str            # tamamlanan cumle
    chunk_no: int


_SIGNALS = {
    "decision": [
        r"\bkarar\s+(aldık|verdik|veriyoruz|verildi)\b",
        r"\bonayl(adık|ıyoruz|andı)\b",
        r"\bnet\s*:",
    ],
    "action": [
        r"\b(yapacağız|yapacak|hallederiz|hallederim)\b",
        r"\büstlen(dim|iyorum|di)\b",
        r"\bsorumlu(?:su)?\b",
        r"\b(teslim|bitirir|gonderir)(im|iz|ecek|ir)\b",
        r"\byarın\b|\bcuma(?:'ya)?\b|\bPazartesi\b",   # deadline sinyali
    ],
}


class SignalDetector:
    """Tamamlanan cumlelerde operasyonel sinyal arar."""

    def __init__(self):
        self._compiled = {k: [re.compile(p, re.IGNORECASE)
                              for p in v] for k, v in _SIGNALS.items()}

    def scan(self, sentence: str, chunk_no: int) -> list[LiveEvent]:
        events = []
        for kind, patterns in self._compiled.items():
            if any(p.search(sentence) for p in patterns):
                events.append(LiveEvent(kind=kind, text=sentence,
                                        chunk_no=chunk_no))
        return events
