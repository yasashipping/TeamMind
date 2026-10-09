"""
app/db/search.py — Toplanti ici arama (Modul 2).

PostgreSQL hedefi: tsvector + ts_rank (bkz. SQL_PG asagida).
Test kolayligi icin SQLite FTS5 uygulamasi da mevcut: sorgu semantigi
(rank + agirlik) iki backend'de de ayni.

Agirlik semantigi: karar/aksiyon/risk gibi operasyonel metinler (B)
dusuk olsa da alakali; ham transkript (A) esit — gercek farklilik
'item_type' filtresiyle API katmaninda yapilir.
"""
from __future__ import annotations

import sqlite3

SQL_PG = """
CREATE INDEX idx_seg_search ON transcript_segments
  USING gin(to_tsvector('turkish', text));
CREATE INDEX idx_items_search ON extracted_items
  USING gin(to_tsvector('turkish', text));

SELECT m.id, m.title, m.meeting_date,
       ts_rank(to_tsvector('turkish', ts.text), q) +
       ts_rank(to_tsvector('turkish', i.text), q) * 2 AS rank
FROM meetings m
JOIN transcript_segments ts ON ts.meeting_id = m.id
LEFT JOIN extracted_items i ON i.meeting_id = m.id
WHERE to_tsvector('turkish', ts.text) @@ q
   OR to_tsvector('turkish', i.text) @@ q
ORDER BY rank DESC LIMIT :limit;
"""

_SCHEMA = """
CREATE TABLE meetings (id TEXT PRIMARY KEY, title TEXT, meeting_date TEXT);
CREATE TABLE segments (id INTEGER PRIMARY KEY, meeting_id TEXT,
                       speaker TEXT, text TEXT);
CREATE TABLE items (id INTEGER PRIMARY KEY, meeting_id TEXT,
                    item_type TEXT, text TEXT);
CREATE VIRTUAL TABLE search_index USING fts5(
    content, meeting_id UNINDEXED, source UNINDEXED, ref_id UNINDEXED,
    tokenize = 'unicode61');
"""

# FTS5, tsvector'in aksine agirlik vermez; agirligi sorgu sonrasi
# Python'da uygulariz: operasyonel item eslesmeleri x2.
ITEM_TYPES = ("decision", "action_item", "risk")


def connect(path: str = ":memory:") -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(_SCHEMA)
    return con


def index_meeting(con, meeting_id, title, date, segments, items):
    """segments: [(speaker, text)]  items: [(item_type, text)]"""
    con.execute("INSERT INTO meetings VALUES (?,?,?)",
                (meeting_id, title, date))
    for sp, text in segments:
        cur = con.execute(
            "INSERT INTO segments (meeting_id, speaker, text) VALUES (?,?,?)",
            (meeting_id, sp, text))
        con.execute(
            "INSERT INTO search_index (content, meeting_id, source, ref_id)"
            " VALUES (?,?,?,?)",
            (text, meeting_id, "transcript", str(cur.lastrowid)))
    for itype, text in items:
        cur = con.execute(
            "INSERT INTO items (meeting_id, item_type, text) VALUES (?,?,?)",
            (meeting_id, itype, text))
        con.execute(
            "INSERT INTO search_index (content, meeting_id, source, ref_id)"
            " VALUES (?,?,?,?)",
            (text, meeting_id, itype, str(cur.lastrowid)))
    con.commit()


import re as _re

_SAFE = _re.compile(r"[^0-9a-z\u00e7\u011f\u0131\u00f6\u015f\u00fc"
                    r"\u00c7\u011e\u0130\u00d6\u015e\u00dc]+")

def _fts_query(q: str) -> str:
    """Kullanici girdisini guvenli FTS5 sorgusuna cevirir.

    - Guvenlik: FTS5 operator/quote karakterleri tamamen temizlenir
      (enjeksiyon en aza iner; kalan risk sadece gereksiz eslesmedir).
    - Semantik: kelimelerin HER BIRI ile eslesme (AND).
    - TR ek-yogun dil: her terim onek (prefix) eslesmesi yapar
      ("butce" -> "butce", "butcesi", "butcemiz"...).
    """
    parts = []
    for raw in q.split():
        clean = _SAFE.sub(" ", tr_lower_local(raw)).strip()
        parts.extend(clean.split())
    if not parts:
        return '""'
    return " AND ".join(f'"{p}"*' for p in parts)


def tr_lower_local(s: str) -> str:
    return s.replace("I", "\u0131").replace("\u0130", "i").lower()


def search(con, q: str, limit: int = 20):
    """Donen: [{meeting_id, title, date, source, snippet, score}]
    score: FTS5 bm25 tabanli ham skor x tur agirligi (item=2, transkript=1).
    bm25 negatiftir (kucuk = iyi); skora cevirirken isaret ters cevrilir."""
    import re as _re2
    fq = _fts_query(q)
    terms = [t.strip('"').rstrip("*") for t in fq.split(" AND ") if t != '""']
    rows = con.execute(
        "SELECT meeting_id, source, ref_id, content,"
        "       bm25(search_index) AS bm"
        " FROM search_index WHERE search_index MATCH ?"
        " ORDER BY bm LIMIT ?",
        (fq, limit * 5)).fetchall()

    weight = lambda src: 2.0 if src in ITEM_TYPES else 1.0

    def _score(content, src, bm):
        """bm25 prefix sorgularda 0 donebilir (SQLite davranisi) -> bu
        durumda terim eslesme sayisiyla deterministik skorlama yapilir.
        Agirlik: karar/aksiyon/risk = 2x."""
        base = -bm if bm else 0.0
        if base < 0.001:   # prefix sorgularda bm25 ~1e-6 donebilir
            low = tr_lower_local(content)
            base = float(sum(len(_re2.findall(_re2.escape(t), low))
                             for t in terms)) or 1.0
        return round(base * weight(src), 4)

    scored = [{
        "meeting_id": mid,
        "source": src,
        "snippet": content[:160],
        "score": _score(content, src, bm),
    } for mid, src, ref, content, bm in rows]

    scored.sort(key=lambda r: r["score"], reverse=True)

    # meeting basligi icin birlestir
    out, seen = [], set()
    for r in scored:
        meta = con.execute("SELECT title, meeting_date FROM meetings"
                           " WHERE id=?", (r["meeting_id"],)).fetchone()
        r["title"], r["date"] = (meta or ("?", "?"))
        out.append(r)
        if len(out) >= limit:
            break
    return out
