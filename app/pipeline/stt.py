"""
app/pipeline/stt.py — Gercek STT motoru (Faz 0 spike icin hazir).

Iki backend:
  - "faster_whisper" (varsayilan): kurulumu kolay, CPU'da bile calisir,
    VAD filtresi ve kelime zaman damgasi icerir. Spike'ta bunu kullan.
  - "whisperx": GPU + HuggingFace token gerektirir; diarization
    (konusmaci ayrirma) icin Faz 1'de gecilecek.

Donus degeri her zaman list[TranscriptLine] — pipeline geri kalanina
dokunulmaz.
"""
from __future__ import annotations

import os

from app.core.config import settings
from app.schemas.analysis import TranscriptLine


def normalize_audio(src_path: str, work_dir: str = ".") -> str:
    """Herhangi bir sesi (mp4/m4a/mp3/wav) 16kHz mono WAV'a cevirir.

    Harici ffmpeg GEREKTIRMEZ: faster-whisper'in bagimliligi olan PyAV
    (gömülü FFmpeg kitapliklari) kullanilir.
    """
    import av
    import numpy as np
    import wave

    container = av.open(src_path)
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)

    pcm_parts = []
    for frame in container.decode(stream):
        for rframe in resampler.resample(frame):
            pcm_parts.append(rframe.to_ndarray().reshape(-1))
    # kalan tampon
    for rframe in resampler.resample(None):
        pcm_parts.append(rframe.to_ndarray().reshape(-1))

    pcm = np.concatenate(pcm_parts).astype(np.int16)
    out = os.path.join(work_dir, "_normalized.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())
    return out


class STTEngine:
    def __init__(self, backend: str = "faster_whisper"):
        self.backend = backend
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        if self.backend == "faster_whisper":
            from faster_whisper import WhisperModel
            # CPU: int8 (hizli, dusuk bellek). GPU varsa float16 onerilir.
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            compute = "float16" if device == "cuda" else "int8"
            self._model = WhisperModel(
                settings.whisper_model_size,
                device=device, compute_type=compute)
        else:
            raise NotImplementedError("whisperx backend'i Faz 1'de eklenir")

    def transcribe(self, audio_path: str) -> list[TranscriptLine]:
        self._load()
        wav = normalize_audio(audio_path)
        try:
            segments, _info = self._model.transcribe(
                wav,
                language="tr",               # Turkce toplantilar
                vad_filter=True,             # sessizlik/parazit atilir
                word_timestamps=True,
                beam_size=5,
                condition_on_previous_text=False,  # halüsinasyon zincirini kirar
            )
            return [
                TranscriptLine(speaker_label="",   # spike'ta diarization yok
                               start_sec=s.start,
                               end_sec=s.end,
                               text=s.text.strip())
                for s in segments
            ]
        finally:
            if os.path.exists(wav):
                os.remove(wav)      # gizlilik: ara dosya silinir
