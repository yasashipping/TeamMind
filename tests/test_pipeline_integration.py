"""
Entegrasyon testi: process_meeting akisinin konusmaci eslestirmeyi
dogru sirada ve dogru semantikle uyguladigini dogrular.
STT ve LLM mocklanir; gercek birim: SpeakerMatcher + _apply_matches.
"""
from unittest.mock import patch

from app.pipeline import tasks
from app.pipeline.tasks import process_meeting, _apply_matches
from app.db import store
from app.schemas.analysis import TranscriptLine

FAKE_LINES = [
    TranscriptLine(speaker_label="S1", start_sec=0.0, end_sec=4.0,
        text="Ben Ahmet, bugun Q4 butcesini konusalim."),
    TranscriptLine(speaker_label="S2", start_sec=4.5, end_sec=9.0,
        text="Elif, sen gelir tablosunu hazirlar misin?"),
    TranscriptLine(speaker_label="S2", start_sec=9.5, end_sec=13.0,
        text="Hazirlarim, cuma'ya kadar gonderirim."),
]

class FakeTopic:
    def __init__(self):
        self.title = "Q4 butcesi"; self.type = "agenda"
        self.line_start = 0; self.line_end = 3

class FakeSegmentation:
    topics = [FakeTopic()]

class FakeExtraction:
    items = []

class FakeQuality:
    kept_items = []; removed_items = []; executive_summary = "ozet"


def test_full_pipeline_applies_speaker_names():
    m_id = "mtg-test-1"
    with patch.object(tasks.stt_engine, "transcribe",
                      return_value=FAKE_LINES), \
         patch.object(tasks.llm, "segment",
                      return_value=FakeSegmentation()), \
         patch.object(tasks.llm, "extract",
                      return_value=FakeExtraction()), \
         patch.object(tasks.llm, "filter_and_summarize",
                      return_value=FakeQuality()), \
         patch.object(tasks.os, "remove"):
        process_meeting.run(m_id, "/tmp/x.m4a",
                            participant_candidates=["Ahmet Yilmaz", "Elif Kaya"])

    st = store.get(m_id)
    statuses = [s for s, _ in st["log"]]
    assert statuses == ["processing_stt", "matching_speakers", "analyzing", "done"]
    matches = {m.label: m for m in st["matches"]}
    assert matches["S1"].status == "auto" and matches["S1"].name == "Ahmet Yilmaz"
    assert matches["S2"].status == "unmatched" and matches["S2"].name is None
    labels = [l.speaker_label for l in st["transcript"]]
    assert labels[0] == "Ahmet Yilmaz" and labels[1] == "S2" and labels[2] == "S2"


def test_apply_matches_never_invents_names():
    from app.pipeline.speaker_matching import SpeakerMatch
    matches = [SpeakerMatch("S1", "Ahmet Yilmaz", 0.98, "auto"),
               SpeakerMatch("S2", None, 0.5, "needs_review")]
    out = _apply_matches(FAKE_LINES, matches)
    assert out[0].speaker_label == "Ahmet Yilmaz"
    assert out[1].speaker_label == "S2"
