"""
app/pipeline/export.py — Rapor uretimi (Modul 3).

Tek veri modelinden iki cikti:
  - HTML (jinja2)  -> PDF'e donusturulebilir (weasyprint varsa)
  - DOCX (python-docx)

Girdi: pipeline'in nihai ciktisi (store'dan gelen sozluk):
{
  "title": ..., "date": ..., "participants": [...],
  "executive_summary": ...,
  "items": [ExtractedItem dict'leri ...]
}
"""
from __future__ import annotations

import os

from jinja2 import Template

from app.schemas.analysis import ExtractedItem

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__),
                             "templates", "report.html")

SECTION_ORDER = ["decision", "action_item", "risk",
                 "open_question", "idea"]


def build_report_data(meeting: dict) -> dict:
    """Ham pipeline ciktisini sablonun bekledigi sekle getirir."""
    items = [ExtractedItem.model_validate(i) for i in meeting["items"]]
    grouped = {k: [i for i in items if i.type == k] for k in SECTION_ORDER}
    return {
        "title": meeting.get("title", "Toplantı Raporu"),
        "date": meeting.get("date", ""),
        "participants": meeting.get("participants", []),
        "executive_summary": meeting.get("executive_summary", ""),
        "decisions": grouped["decision"],
        "action_items": grouped["action_item"],
        "risks": grouped["risk"],
        "open_questions": grouped["open_question"],
        "ideas": grouped["idea"],
    }


def render_html(report: dict) -> str:
    tpl = Template(open(TEMPLATE_PATH, encoding="utf-8").read())
    return tpl.render(**report)


def export_pdf(report: dict) -> bytes:
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError(
            "PDF uretimi icin weasyprint gerekli: pip install weasyprint "
            "(HTML ciktisi render_html() ile simdi kullanilabilir)") from e
    return HTML(string=render_html(report)).write_pdf()


def export_docx(report: dict, path: str) -> str:
    from docx import Document

    doc = Document()
    doc.add_heading(report["title"], level=0)
    doc.add_paragraph(
        f"Tarih: {report['date']}    Katılımcılar: "
        + ", ".join(report["participants"]))

    doc.add_heading("Yönetici Özeti", level=1)
    doc.add_paragraph(report["executive_summary"])

    def _items(items, level=2):
        for it in items:
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(it.text)
            if it.owner:
                p.add_run(f"  (sorumlu: {it.owner})").bold = True
            if it.deadline:
                p.add_run(f"  [son: {it.deadline}]")
            if it.confidence < 0.7:
                p.add_run(f"  (düşük güven %{it.confidence:.0f})").italic = True

    if report["decisions"]:
        doc.add_heading("Kararlar", level=1)
        _items(report["decisions"])
    if report["action_items"]:
        doc.add_heading("Aksiyon Maddeleri", level=1)
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = (
            "Görev", "Sorumlu", "Son Tarih", "Güven")
        for a in report["action_items"]:
            row = table.add_row().cells
            row[0].text = a.text
            row[1].text = a.owner or "—"
            row[2].text = a.deadline or "—"
            row[3].text = f"%{a.confidence:.0f}"
    if report["risks"]:
        doc.add_heading("Riskler ve Problemler", level=1)
        _items(report["risks"])
    if report["open_questions"]:
        doc.add_heading("Açık Sorular", level=1)
        _items(report["open_questions"])
    if report["ideas"]:
        doc.add_heading("Önemli Fikirler", level=1)
        _items(report["ideas"])

    doc.save(path)
    return path
