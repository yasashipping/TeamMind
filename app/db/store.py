"""app/db/store.py — DB erisim katmani (arayuz).

Implementasyon SQLAlchemy ile doldurulacak; simdilik bellek icinde tutar
ki pipeline test edilebilsin.
"""
from __future__ import annotations

STATUS_ORDER = ["uploaded", "processing_stt", "matching_speakers",
                "analyzing", "done", "failed"]

_meetings: dict = {}


def update_status(meeting_id: str, status: str, note: str | None = None):
    _meetings.setdefault(meeting_id, {"status": None, "log": []})
    _meetings[meeting_id]["status"] = status
    _meetings[meeting_id]["log"].append((status, note))
    print(f"[{meeting_id}] status -> {status}" + (f" | {note}" if note else ""))


def save_transcript(meeting_id, lines):
    _meetings.setdefault(meeting_id, {})["transcript"] = lines


def save_participant_matches(meeting_id, matches):
    _meetings.setdefault(meeting_id, {})["matches"] = list(matches)


def save_analysis(meeting_id, topics, quality):
    _meetings.setdefault(meeting_id, {})["analysis"] = quality


def get(meeting_id):
    return _meetings.get(meeting_id)
