from pydantic import BaseModel, Field
from typing import Literal, Optional


# ---------- Transkript (STT ciktisi) ----------
class TranscriptLine(BaseModel):
    speaker_label: str
    start_sec: float
    end_sec: float
    text: str


# ---------- Asama 1: Segmentasyon ----------
class Topic(BaseModel):
    title: str
    type: Literal["agenda", "casual"]
    line_start: int
    line_end: int
    summary: str


class SegmentationResult(BaseModel):
    topics: list[Topic]


# ---------- Asama 2: Bilgi Cikarimi ----------
class ExtractedItem(BaseModel):
    type: Literal["decision", "action_item", "risk",
                  "open_question", "idea"]
    text: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    evidence: str
    line_no: int
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    items: list[ExtractedItem]


# ---------- Asama 3: Kalite Filtresi ----------
class RemovedItem(BaseModel):
    text: str
    reason: str


class QualityResult(BaseModel):
    kept_items: list[ExtractedItem]
    removed_items: list[RemovedItem]
    executive_summary: str


# ---------- Konusmaci eslestirme (Modul 1) ----------
class ParticipantMatch(BaseModel):
    speaker_label: str
    display_name: Optional[str]      # needs_review/unmatched ise null
    status: Literal["auto", "inferred", "needs_review", "unmatched"]
    confidence: float
