
from app.pipeline.speaker_matching import (
    SpeakerMatcher, TranscriptLine, tr_lower, first_name)

matcher = SpeakerMatcher()

def L(label, text):
    return TranscriptLine(speaker_label=label, text=text)

# ------------------------------------------------ temel sinyal testleri

def test_turkish_lowercase():
    assert tr_lower("Istanbul IGLIK") == "\u0131stanbul \u0131gl\u0131k"
    assert first_name("Ahmet YILMAZ") == "ahmet"
    assert first_name("\u0130pek DEM\u0130R") == "ipek"

def test_self_intro_scores_highest():
    lines = [L("S1", "Ben Ahmet, bugun proje durumunu konusacagiz."),
             L("S2", "Tamam, ben de sunumlari hazirladim.")]
    report = matcher.match(lines, ["Ahmet Yilmaz", "Elif Kaya"])
    assert report.auto_matched() == {"S1": "Ahmet Yilmaz"}

def test_address_is_negative_and_report_verbs_are_mentions():
    lines = [L("S1", "Elif, sen butce tablosunu hazirlar misin?"),
             L("S2", "Hazirlarim, yarin gonderirim."),
             L("S1", "Ahmet dedi ki deadline cuma olacakmis."),
             L("S2", "Anladim, o zaman cuma'ya yetistiririm.")]
    report = matcher.match(lines, ["Ahmet Yilmaz", "Elif Kaya"])
    s1 = next(m for m in report.matches if m.label == "S1")
    # "Elif, sen..." -> S1 Elif OLAMAZ (-1.0); "Ahmet dedi ki" -> anma (+0.5)
    # fark 1.5 vs -1.0 -> auto
    assert s1.name == "Ahmet Yilmaz" and s1.status == "auto"
    s2 = next(m for m in report.matches if m.label == "S2")
    assert s2.status == "unmatched"

def test_ambiguous_goes_to_review():
    lines = [L("S1", "Ahmet ve Elif ikisi de toplantida.")]
    report = matcher.match(lines, ["Ahmet Yilmaz", "Elif Kaya"])
    assert report.matches[0].status == "needs_review"
    assert report.matches[0].name is None

def test_unmatched_when_no_signal():
    lines = [L("S3", "Butce konusuna gecelim simdiden.")]
    report = matcher.match(lines, ["Ahmet Yilmaz", "Elif Kaya"])
    assert report.matches[0].status == "unmatched"

def test_confidence_is_ratio():
    lines = [L("S1", "Selam, ben Ahmet.")]
    report = matcher.match(lines, ["Ahmet Yilmaz", "Elif Kaya"])
    assert report.matches[0].confidence >= 0.99

def test_case_and_turkish_i():
    lines = [L("S1", "BEN AHMET, baslayalim.")]
    report = matcher.match(lines, ["Ahmet Yilmaz"])
    assert report.matches[0].status == "auto"

def test_report_verb_at_start_counts_as_mention():
    # "Ahmet dedi ki..." ile baslayan satirda konusan Ahmet'i anlatiyor;
    # 3. sahis anmasi +0.5, adres -1.0 DEGIL.
    lines = [L("S1", "Ahmet dedi ki butce onaylandi.")]
    scores = {c: matcher.score(lines, c) for c in ["Ahmet Yilmaz", "Elif Kaya"]}
    assert scores["Ahmet Yilmaz"] == 0.5
