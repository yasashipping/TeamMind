"""run_analyze.py — Gercek transkript -> Claude analizi -> rapor.

Kullanim (spike'tan sonra):
    python run_analyze.py toplantim_transkript.txt

Zincir: transkript dosyasi -> segmentasyon -> cikari m -> kalite + ozet.
Cikti: ekran + toplantim_transkript_raporu.md
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline import llm


def load_transcript(path: str) -> str:
    """Spike ciktisi (satir no | sure | metin) veya duz metin her ikisi de olur."""
    lines = open(path, encoding="utf-8").read().splitlines()
    numbered = []
    for i, line in enumerate(lines):
        parts = [p.strip() for p in line.split("|")]
        text = parts[-1]                 # son parca her zaman metin
        numbered.append(f"{i} | {text}")
    return "\n".join(numbered)


def main():
    if len(sys.argv) < 2:
        sys.exit("Kullanim: python run_analyze.py <transkript.txt>")
    path = sys.argv[1]
    transcript = load_transcript(path)
    print(f"Transkript yuklendi: {len(transcript.splitlines())} satir\n")

    print("== 1. SEGMENTASYON ==")
    seg = llm.segment(transcript)
    for t in seg.topics:
        print(f"  [{t.type}] {t.title} (satir {t.line_start}-{t.line_end})")

    all_items = []
    for t in seg.topics:
        if t.type != "agenda":
            continue
        lines = transcript.splitlines()
        seg_text = "\n".join(lines[t.line_start:t.line_end + 1])
        print(f"\n== 2. CIKARIM: {t.title} ==")
        ext = llm.extract(t.title, seg_text, t.line_start, t.line_end)
        for it in ext.items:
            print(f"  [{it.type}] {it.text} | owner={it.owner} "
                  f"dl={it.deadline} conf={it.confidence}")
        all_items.extend(i.model_dump() for i in ext.items)

    print("\n== 3. KALITE FILTRESI + OZET ==")
    q = llm.filter_and_summarize(json.dumps(all_items, ensure_ascii=False))
    print("  OZET:", q.executive_summary)
    print(f"  Tutulan: {len(q.kept_items)} | Elenen: {len(q.removed_items)}")

    out_md = os.path.splitext(path)[0] + "_raporu.md"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(f"# Toplantı Raporu\n\n## Yönetici Özeti\n{q.executive_summary}\n")
        for kind, label in [("decision", "Kararlar"),
                            ("action_item", "Aksiyon Maddeleri"),
                            ("risk", "Riskler"),
                            ("open_question", "Açık Sorular"),
                            ("idea", "Fikirler")]:
            items = [i for i in q.kept_items if i.type == kind]
            if items:
                f.write(f"\n## {label}\n")
                for i in items:
                    owner = f" — {i.owner}" if i.owner else ""
                    dl = f" (son: {i.deadline})" if i.deadline else ""
                    f.write(f"- {i.text}{owner}{dl}\n")
    print(f"\nRapor yazildi -> {out_md}")


if __name__ == "__main__":
    main()
