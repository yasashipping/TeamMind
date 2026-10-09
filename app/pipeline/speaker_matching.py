
# app/pipeline/speaker_matching.py
"""
Konuşmaci eslestirme modulu.

Diarization ciktisi "Speaker 1" gibi etiketler uretir. Bu modul, transkript
icindeki isim sinyallerini skorlayarak her etiketi katilimci listesindeki
bir isimle eslestirir.

Sinyal semantikleri:
- SELF_INTRO (+3.0): satiri konusan kisi kendini tanitiyor
  ("Ben Ahmet", "Benim adim Elif"). En guvenilir sinyal.
- ADDRESS (-1.0): satir bir isimle basliyor -> konusan o kisi DEGILDIR
  ("Elif, sen bakar misin?" diyen kisi Elif olamaz).
- MENTION (+0.5): 3. sahis anma ("Ahmet dedi ki..."). Zayif sinyal.

Istisna: isimle baslayan ama "dedi/diyor/soyledi" ile devam eden satirlar
3. sahis anmasidir, adres degil -> MENTION uygulanir.

Eslestirme kurallari:
- En iyi aday, ikinciden >= MARGIN_RATIO kat buyukse -> 'auto'
- Belirsizse -> 'needs_review' (kullanici arayuzunde dogrulanir, isim atanmaz)
- En iyi skor <= 0 ise -> 'unmatched'

Turkce notu: "I" -> "i" (noktali) degil "i" (noktasiz) donusur; bu yuzden
tr_lower kullanilir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


def tr_lower(text: str) -> str:
    """Turkceye uygun kucuk harf donusumu (I -> i, i -> i)."""
    return (text.replace("I", "\u0131")
                .replace("\u0130", "i")
                .lower())


def first_name(full_name: str) -> str:
    """'Ahmet Yilmaz' -> 'ahmet' (Turkce kucuk harfli)."""
    return tr_lower(full_name.split()[0])


def _bounded(name: str) -> str:
    """Kelime sinirli, regex-escapeli parca."""
    return rf"(?<!\w){re.escape(name)}(?!\w)"


@dataclass
class TranscriptLine:
    speaker_label: str
    text: str


@dataclass
class SpeakerMatch:
    label: str
    name: Optional[str]
    confidence: float
    status: str                      # 'auto' | 'needs_review' | 'unmatched'


@dataclass
class MatchReport:
    matches: list[SpeakerMatch] = field(default_factory=list)

    def auto_matched(self) -> dict[str, str]:
        return {m.label: m.name for m in self.matches if m.status == "auto"}


class SpeakerMatcher:
    W_SELF_INTRO = 3.0     # "Ben Ahmet", "Benim adim Elif"
    W_ADDRESS    = -1.0    # NEGATIF: konusan, hitap edilen kisi olamaz
    W_MENTION    = 0.5     # 3. sahis anma: "Ahmet dedi ki..."
    MARGIN_RATIO = 2.0     # en az 2x fark -> otomatik eslestirme

    # isimle baslayan satirlarda adres OLMAYAN kalip: "Ahmet dedi ki..."
    _REPORT_VERBS = ("dedi", "diyor", "soyledi", "soyluyor", "belirtti")
    # gercek hitap kaliplarinin isaretleri: virgul ("Elif,") ya da 2. sahis
    _SECOND_PERSON = ("sen", "siz", "senin", "sizin", "sana", "size",
                      "seni", "sizi", "seninle", "sizinle", "ne dersin",
                      "ne diyorsun", "ne dusunuyorsun")

    def _is_address(self, line_text: str, fn: str) -> bool:
        """Satir gercekten bir hitap mi, yoksa 3. sahis anmasi mi?

        Hitap kalibi: isim + virgul ("Elif, ...") veya isim + 2. sahis
        zamir/soru ("Elif sen bakar misin?"). "Ahmet ve Elif ..." ve
        "Ahmet dedi ki ..." gibi satirlar adres degil, 3. sahis anmasidir.
        """
        if not re.match(rf"^{_bounded(fn)}\b", line_text):
            return False
        rest = re.sub(rf"^{_bounded(fn)}\b", "", line_text, count=1).strip()
        if not rest:
            return False                    # isimden baska bir sey yok -> anma
        if rest.startswith(","):
            return True
        first_words = " ".join(rest.split()[:2]).lower()
        return any(first_words.startswith(w) for w in self._SECOND_PERSON)

    def score(self, lines: list[TranscriptLine], candidate: str) -> float:
        fn = first_name(candidate)
        total = 0.0
        for line in lines:
            t = tr_lower(line.text)
            if re.search(rf"\bben(?:im)?(?:\s+ad\w*m)?\s+{_bounded(fn)}", t):
                total += self.W_SELF_INTRO
            elif self._is_address(t, fn):
                total += self.W_ADDRESS       # konusan != hitap edilen
            elif re.search(_bounded(fn), t):
                total += self.W_MENTION
        return total

    def match(self, lines: list[TranscriptLine],
              candidates: list[str]) -> MatchReport:
        labels = sorted({l.speaker_label for l in lines})
        # Kritik: her etiket YALNIZCA kendi satirlari uzerinden skorlanir.
        by_label = {lab: [l for l in lines if l.speaker_label == lab]
                    for lab in labels}
        raw = {lab: {c: self.score(by_label[lab], c) for c in candidates}
               for lab in labels}

        report = MatchReport()
        for lab in labels:
            scores = sorted(raw[lab].items(),
                            key=lambda kv: kv[1], reverse=True)
            best_name, best = scores[0]
            second = scores[1][1] if len(scores) > 1 else 0.0

            if best <= 0:
                report.matches.append(SpeakerMatch(lab, None, 0.0, "unmatched"))
            elif best >= self.MARGIN_RATIO * max(second, 0.01):
                conf = round(best / (best + max(second, 0.0) + 0.01), 2)
                report.matches.append(SpeakerMatch(lab, best_name, conf, "auto"))
            else:
                conf = round(best / (best + max(second, 0.0) + 0.01), 2)
                report.matches.append(
                    SpeakerMatch(lab, None, conf, "needs_review"))
        return report
