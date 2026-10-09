"""run_spike.py — Faz 0 spike: gercek ses -> Turkce transkript.

Kullanim:
    python run_spike.py toplantim.m4a

Kurulum (tek seferlik):
    pip install faster-whisper torch
    # harici ffmpeg gerekmez — ses cevirisi PyAV ile icra edilir

Degerlendirme: ciktiyi run_spike_degerlendirme.md'deki kriterlerle inceleyin.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.pipeline.stt import STTEngine


def main():
    if len(sys.argv) < 2:
        sys.exit("Kullanim: python run_spike.py <ses_dosyasi>")
    audio = sys.argv[1]
    if not os.path.exists(audio):
        sys.exit(f"Dosya bulunamadi: {audio}")

    print(f"Isleniyor: {audio}")
    engine = STTEngine()
    lines = engine.transcribe(audio)

    out_txt = os.path.splitext(audio)[0] + "_transkript.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        for i, l in enumerate(lines):
            f.write(f"{i} | {l.start_sec:7.1f}s | {l.text}\n")
    print(f"\n{len(lines)} segment yazildi -> {out_txt}\n")
    for i, l in enumerate(lines[:15]):
        print(f"{i} | {l.start_sec:7.1f}s | {l.text}")
    if len(lines) > 15:
        print(f"... ({len(lines) - 15} segment daha)")


if __name__ == "__main__":
    main()
