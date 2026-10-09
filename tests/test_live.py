"""
Modul 4 (canli dinleme cekirdegi) testleri — metin simulasyonu.
Ses/chunk uretimi mocklanir; algoritmalar gercek.
"""
from app.pipeline.live import (
    ChunkResult, RollingAssembler, SignalDetector, LiveEvent)


def test_overlap_is_stripped():
    a = RollingAssembler()
    # onceki chunk'un sonuyle yeni chunk'un basi ortusuyor
    a.feed(ChunkResult("Bütçeyi konuşalım, sonra da ekibi toplayalım", chunk_no=1))
    out = a.feed(ChunkResult("ekibi toplayalım ve yarın karar verelim.", chunk_no=2))
    joined = " ".join(out)
    assert "ekibi toplayalım" in joined
    assert joined.count("ekibi toplayalım") == 1   # tekrar YOK


def test_half_sentence_completes_across_chunks():
    a = RollingAssembler()
    out1 = a.feed(ChunkResult("Bence bütçeyi yarın", is_final=False, chunk_no=1))
    assert out1 == []                      # yarim cumle yayinlanmaz
    out2 = a.feed(ChunkResult("konuşalım, sonra netleşir.", is_final=True, chunk_no=2))
    assert out2 == ["Bence bütçeyi yarın konuşalım, sonra netleşir."]


def test_final_chunk_flushes_buffer():
    a = RollingAssembler()
    out = a.feed(ChunkResult("Son bir konu kaldı, yarın görüşürüz", is_final=True, chunk_no=3))
    assert len(out) == 1 and "görüşürüz" in out[0]


def test_detector_fires_on_decision_and_action():
    d = SignalDetector()
    evs = d.scan("Bütçe 4.5M olarak onaylandı, karar verdik.", chunk_no=1)
    kinds = {e.kind for e in evs}
    assert "decision" in kinds

    evs2 = d.scan("Elif raporu hazırlar, yarın gönderir.", chunk_no=2)
    assert any(e.kind == "action" for e in evs2)


def test_detector_ignores_casual():
    d = SignalDetector()
    assert d.scan("Kahve molası sonrası devam edelim.", chunk_no=1) == []
    assert d.scan("Hava bugün çok güzelmiş.", chunk_no=2) == []


def test_live_loop_end_to_end():
    """Simule chunk dizisi -> birlesik cumleler + olaylar."""
    chunks = [
        ChunkResult("Selam herkese, bence bütçeyi", is_final=False, chunk_no=0),
        ChunkResult("bütçeyi konuşalım. Elif raporu", is_final=False, chunk_no=1),
        ChunkResult("raporu hazırlar, yarın gönderir.", is_final=False, chunk_no=2),
        ChunkResult("Karar: toplantıyı erken bitirelim, karar verdik.", is_final=True, chunk_no=3),
    ]
    a, det = RollingAssembler(), SignalDetector()
    sentences, events = [], []
    for c in chunks:
        for s in a.feed(c):
            sentences.append(s)
            events.extend(det.scan(s, c.chunk_no))
    assert any("bütçeyi konuşalım" in s for s in sentences)
    assert any("hazırlar, yarın gönderir" in s for s in sentences)
    kinds = {e.kind for e in events}
    assert "decision" in kinds and "action" in kinds
