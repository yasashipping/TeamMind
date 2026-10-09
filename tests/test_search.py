"""
Modul 2 (arama) testleri — SQLite FTS5 uzerinde.
PostgreSQL tsvector surumu ayni semantigi tasimali.
"""
from app.db import search


def _seed():
    con = search.connect()
    # Toplanti A: "butce" yalnizca gundelik konusmada geciyor
    search.index_meeting(
        con, "A", "Haftalik sync", "2026-09-21",
        segments=[("Ahmet", "Butce konusunu yarin konusuruz artik."),
                  ("Elif", "Peki, sunuma geceyim.")],
        items=[("idea", "Sunum aralara bir kahve molasi konabilir.")])
    # Toplanti B: "butce" bir KARAR'da geciyor
    search.index_meeting(
        con, "B", "Q4 planlama", "2026-09-23",
        segments=[("Ahmet", "Butce rakamlarina bakalim."),
                  ("Elif", "Tabloyu actim.")],
        items=[("decision", "Q4 butcesi 4.5M TL olarak onaylandi."),
               ("action_item", "Elif butce gerceklesme raporunu Pazar'a kadar gonderir.")])
    return con


def test_operational_item_outranks_casual_mention():
    con = _seed()
    res = search.search(con, "butce")
    assert len(res) >= 3
    # Niyet: operasyonel icerik (karar/aksiyon) gundelik konusmayi gecer.
    # Karar ile aksiyon ayni agirliktadir; ikisi de transkriptlerin ustundedir.
    assert res[0]["meeting_id"] == "B"
    assert res[0]["source"] in ("decision", "action_item")
    # Gundelik konusma (A) ilk iki sirada olmamali
    assert all(r["meeting_id"] == "B" for r in res[:2])
    assert res[0]["score"] > res[-1]["score"]


def test_and_semantics():
    con = _seed()
    res = search.search(con, "butce onaylandi")
    assert res, "AND sorgusu eslesme bulmali"
    assert all(r["meeting_id"] == "B" for r in res[:2])


def test_no_match_returns_empty():
    con = _seed()
    assert search.search(con, "falafel") == []


def test_malicious_query_is_neutralized():
    con = _seed()
    # FTS operator enjeksiyonu hata FIRLATMAMALI
    res = search.search(con, 'butce" OR 1=1 --')
    assert isinstance(res, list)


def test_limit_respected():
    con = _seed()
    assert len(search.search(con, "butce", limit=2)) <= 2
