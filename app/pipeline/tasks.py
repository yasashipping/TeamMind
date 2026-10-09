"""
app/pipeline/tasks.py — MeetMind ana islem hatti (Celery).

Akis:
    STT+diarization ──▶ KONUSMACI ESLESTIRME (Modul 1) ──▶ Segmentasyon
                      ──▶ Cikari m ──▶ Kalite filtresi + ozet

Eslestirme neden analizden ONCE: LLM ciktilarinda 'owner' alanlari
Speaker etiketi yerine gercek isimle tutarli olmali; ayrica rapor
katilimcilar bolumu bu adimin ciktisindan beslenir.
"""
from __future__ import annotations

import json
import os

try:
    from celery import Celery, group
except ImportError:  # test ortami: shim kullan
    from app.pipeline._celery_shim import Celery, group

from app.core.config import settings
from app.pipeline.stt import STTEngine
from app.pipeline import llm
from app.pipeline.speaker_matching import SpeakerMatcher
from app.db import store

celery = Celery("meetmind", broker=settings.redis_url,
                backend=settings.redis_url)
stt_engine = STTEngine()
matcher = SpeakerMatcher()


def _apply_matches(lines, matches):
    """Transkript satirlarindaki Speaker etiketlerini gercek isimlerle
    degistirir; dogrulanmamis (needs_review/unmatched) etiketler
    degistirilmez — uydurma isim YOK."""
    mapping = {m.label: m.name for m in matches
               if m.status in ("auto", "inferred") and m.name}
    return [l.model_copy(update={"speaker_label":
                                 mapping.get(l.speaker_label,
                                             l.speaker_label)})
            for l in lines]


@celery.task(bind=True, max_retries=2)
def process_meeting(self, meeting_id: str, audio_path: str,
                    participant_candidates: list[str] | None = None):
    try:
        # --- Asama 0: STT + diarization -------------------------------
        store.update_status(meeting_id, "processing_stt")
        lines = stt_engine.transcribe(audio_path)
        # --- Modul 1: Konusmaci eslestirme ----------------------------
        store.update_status(meeting_id, "matching_speakers")
        candidates = participant_candidates or []
        report = matcher.match(lines, candidates)
        store.save_participant_matches(meeting_id, report.matches)
        # Sadece 'auto'/'inferred' eslesen etiketler gercek isme cevrilir
        lines = _apply_matches(lines, report.matches)  # isimli satirlar
        store.save_transcript(meeting_id, lines)      # canonical: isimli
        # LLM'e giden numarali metin de isimli satirlardan kurulur
        numbered = "\n".join(
            f"{i} | {l.speaker_label} | {l.text}"
            for i, l in enumerate(lines))

        # --- Asama 1-3: LLM analiz zinciri ----------------------------
        store.update_status(meeting_id, "analyzing")
        topics = llm.segment(numbered).topics

        job = group(
            extract_topic.s(meeting_id, t.title, t.line_start, t.line_end,
                            [l.text for l in lines])
            for t in topics if t.type == "agenda")
        result = job.apply_async().get()

        quality = llm.filter_and_summarize(
            json.dumps([item.model_dump() for batch in result for item in batch],
                       ensure_ascii=False))
        store.save_analysis(meeting_id, topics, quality)

        store.update_status(meeting_id, "done")
        os.remove(audio_path)              # gizlilik: sesi sil

    except Exception as exc:
        store.update_status(meeting_id, "failed", note=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery.task
def extract_topic(meeting_id, topic_title, start, end, line_texts):
    segment_text = "\n".join(f"{i + start} | {t}"
                              for i, t in enumerate(line_texts[start:end]))
    return llm.extract(topic_title, segment_text, start, end,
                     meeting_date=store.get(meeting_id).get("date")).items
