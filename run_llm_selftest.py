"""run_llm_selftest.py — Claude anahtariyla uctan uca prompt testi.
Calistirma:  python run_llm_selftest.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline import llm

ORNEK_TRANSKRIPT = """0 | Ahmet Yılmaz | Selam herkese, başlayalım mı?
1 | Elif Kaya | Açım ben, önce bir şeyler yesek mi?
2 | Ahmet Yılmaz | Yemeği sonra konuşuruz. Bence Q4 bütçesine bakalım.
3 | Elif Kaya | Tabloyu açtım. Pazarlama 2M istiyor.
4 | Ahmet Yılmaz | 2M fazla. 1.5 yapalım, ben onaylıyorum.
5 | Elif Kaya | Tamam, 1.5 olsun. Ben revize ederim, yarın gönderirim.
6 | Ahmet Yılmaz | Süper. Bir de stajyer işi vardı.
7 | Elif Kaya | Evet, ilanı kim yazacak belli değil henüz.
8 | Ahmet Yılmaz | Ben yazarım, cuma'ya kadar yayınlarız.
9 | Elif Kaya | Peki. Hava bugün çok sıcakmış bu arada değil mi?
10 | Ahmet Yılmaz | Öyleymiş, klima açık kalsın. Kapanışa geçelim."""


def main():
    print("== 1. SEGMENTASYON ==")
    seg = llm.segment(ORNEK_TRANSKRIPT)
    for t in seg.topics:
        print(f"  [{t.type}] {t.title} (satır {t.line_start}-{t.line_end})")

    print("\n== 2. CIKARIM (ilk agenda bolumu) ==")
    agenda = [t for t in seg.topics if t.type == "agenda"][0]
    lines = ORNEK_TRANSKRIPT.splitlines()
    seg_text = "\n".join(lines[agenda.line_start:agenda.line_end + 1])
    ext = llm.extract(agenda.title, seg_text,
                      agenda.line_start, agenda.line_end,
                      meeting_date="2026-09-23")
    for it in ext.items:
        print(f"  [{it.type}] {it.text} | owner={it.owner} "
              f"dl={it.deadline} conf={it.confidence}")

    print("\n== 3. KALITE FILTRESI + OZET ==")
    q = llm.filter_and_summarize(
        __import__("json").dumps(
            [i.model_dump() for i in ext.items], ensure_ascii=False))
    print("  Özet:", q.executive_summary)
    print(f"  Tutulan: {len(q.kept_items)} | Elenen: {len(q.removed_items)}")


if __name__ == "__main__":
    main()
