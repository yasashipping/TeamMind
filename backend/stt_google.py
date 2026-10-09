"""stt_google.py — Yol B: Google Cloud Speech-to-Text v2 (Chirp 2) — GERCEK TOPLANTI MODU.

Uzun kayitlar (saatlik) icin akis:
  yerel .m4a -> GCS'e yukle -> batch_recognize (asenkron, inline sonuc) -> GCS objesini sil

STTEngine ile ayni arayuz: transcribe(path) -> [Line(start_sec, text)]
Cikti run_analyze.load_transcript formatiyla ("i | sure | metin") uyumlu.

Env:
  GOOGLE_CLOUD_PROJECT
  STT_LOCATION   (chirp_2 icin: europe-west4 / us-central1 ... — bolge listesini kontrol edin)
  GCS_BUCKET     (gecici ses objeleri; lifecycle 1 gun onerilir)
"""
import os
import uuid
from dataclasses import dataclass

from google.cloud import storage
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech


@dataclass
class Line:
    start_sec: float
    text: str
    speaker: str | None = None   # diarization acilirsa "K1", "K2" ...


class GoogleSTTEngine:
    def __init__(self, project: str | None = None, location: str | None = None,
                 bucket: str | None = None, model: str = "chirp_2",
                 language: str = "tr-TR", diarize: bool = False,
                 min_speakers: int = 2, max_speakers: int = 6):
        self.project = project or os.environ["GOOGLE_CLOUD_PROJECT"]
        self.location = location or os.environ.get("STT_LOCATION", "europe-west4")
        self.bucket = bucket or os.environ["GCS_BUCKET"]
        self.model = model
        self.language = language
        self.diarize = diarize
        self.min_speakers, self.max_speakers = min_speakers, max_speakers
        self.speech = SpeechClient(
            client_options={"api_endpoint": f"{self.location}-speech.googleapis.com"})
        self.gcs = storage.Client(project=self.project)

    # ---------- GCS ----------
    def _upload(self, path: str) -> tuple[str, storage.Blob]:
        blob = self.gcs.bucket(self.bucket).blob(f"stt-in/{uuid.uuid4()}.m4a")
        blob.upload_from_filename(path, content_type="audio/mp4")
        return f"gs://{self.bucket}/{blob.name}", blob

    # ---------- STT ----------
    def transcribe(self, path: str, timeout_sec: int = 3600) -> list[Line]:
        gcs_uri, blob = self._upload(path)
        try:
            features = cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
            )
            if self.diarize:
                features.diarization_config = cloud_speech.SpeakerDiarizationConfig(
                    min_speaker_count=self.min_speakers,
                    max_speaker_count=self.max_speakers,
                )
            config = cloud_speech.RecognitionConfig(
                auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
                language_codes=[self.language],
                model=self.model,
                features=features,
            )
            req = cloud_speech.BatchRecognizeRequest(
                recognizer=f"projects/{self.project}/locations/{self.location}/recognizers/_",
                config=config,
                files=[cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)],
                recognition_output_config=cloud_speech.RecognitionOutputConfig(
                    inline_response_config=cloud_speech.InlineOutputConfig()),
            )
            op = self.speech.batch_recognize(request=req)
            resp = op.result(timeout=timeout_sec)          # bloklar; Cloud Run always-on CPU sart
            file_result = resp.results[gcs_uri]
            if file_result.error and file_result.error.message:
                raise RuntimeError(f"STT hatasi: {file_result.error.message}")
            return self._to_lines(file_result.transcript)
        finally:
            try:
                blob.delete()
            except Exception:
                pass

    def _to_lines(self, transcript) -> list[Line]:
        lines: list[Line] = []
        for result in transcript.results:
            if not result.alternatives:
                continue
            alt = result.alternatives[0]
            if not alt.transcript.strip():
                continue
            if self.diarize and alt.words:
                # konusmaci degistikce yeni satir ac
                cur_spk, buf, start = None, [], 0.0
                for w in alt.words:
                    spk = f"K{w.speaker_label}" if w.speaker_label else None
                    if spk != cur_spk and buf:
                        lines.append(Line(start, " ".join(buf), cur_spk))
                        buf = []
                    if not buf:
                        start = w.start_offset.total_seconds()
                    cur_spk = spk
                    buf.append(w.word)
                if buf:
                    lines.append(Line(start, " ".join(buf), cur_spk))
            else:
                start = alt.words[0].start_offset.total_seconds() if alt.words else 0.0
                lines.append(Line(start, alt.transcript.strip()))
        return lines


def to_numbered_transcript(lines: list[Line]) -> str:
    """run_analyze.load_transcript'in okudugu format (speaker varsa araya eklenir)."""
    out = []
    for i, l in enumerate(lines):
        spk = f" | {l.speaker}" if l.speaker else ""
        out.append(f"{i} | {l.start_sec:7.1f}s{spk} | {l.text}")
    return "\n".join(out)


def to_llm_transcript(lines: list[Line]) -> str:
    """Claude'a giden format: 'i | [konusmaci] | metin'."""
    return "\n".join(
        f"{i} | {l.speaker} | {l.text}" if l.speaker else f"{i} | {l.text}"
        for i, l in enumerate(lines))
