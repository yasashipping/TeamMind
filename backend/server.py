"""server.py — Cloud Run API. Flutter buraya POST /process atar.

Akis:
  1. Supabase JWT dogrula (kullanici kim?)
  2. meetings satirini oku, audio_path'i Storage'dan indir
  3. status=transcribing  -> Google STT (stt_google)
  4. status=analyzing     -> mevcut Claude pipeline (app.pipeline.llm)
  5. status=done          -> report_md + items yaz, ses dosyasini sil

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET
  ANTHROPIC_API_KEY, LLM_MODEL, STT_DIARIZE(0/1)
  STT_PROVIDER=deepgram -> DEEPGRAM_API_KEY
  STT_PROVIDER=google   -> GOOGLE_CLOUD_PROJECT, STT_LOCATION, GCS_BUCKET
"""
import os, json, tempfile, traceback
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel
import jwt
from supabase import create_client

# STT saglayici: STT_PROVIDER=deepgram (varsayilan) | google
if os.environ.get("STT_PROVIDER", "deepgram") == "google":
    from stt_google import GoogleSTTEngine as STTEngine, to_numbered_transcript, to_llm_transcript
else:
    from stt_deepgram import DeepgramSTTEngine as STTEngine, to_numbered_transcript, to_llm_transcript
# Mevcut pipeline: repo'daki app/ klasoru Dockerfile ile bu dizine kopyalanir.
from app.pipeline import llm

app = FastAPI(title="MeetMind API")

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
BUCKET = "recordings"


class ProcessReq(BaseModel):
    meeting_id: str


def _user_id_from_jwt(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization eksik")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, os.environ["SUPABASE_JWT_SECRET"],
                             algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"JWT gecersiz: {e}")
    return payload["sub"]


def _set_status(meeting_id: str, status: str, **fields):
    sb.table("meetings").update({"status": status, **fields}).eq("id", meeting_id).execute()


def run_pipeline(meeting_id: str):
    try:
        row = sb.table("meetings").select("*").eq("id", meeting_id).single().execute().data
        audio_path = row["audio_path"]

        # --- ses indir ---
        data = sb.storage.from_(BUCKET).download(audio_path)
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            tmp.write(data)
            local = tmp.name

        # --- 1) STT ---
        _set_status(meeting_id, "transcribing")
        diarize = os.environ.get("STT_DIARIZE", "0") == "1"
        lines = STTEngine(diarize=diarize).transcribe(local)
        transcript_txt = to_numbered_transcript(lines)
        _set_status(meeting_id, "analyzing", transcript=transcript_txt)

        # --- 2) Claude: segment -> extract -> filter (run_analyze.py ile ayni zincir) ---
        numbered = to_llm_transcript(lines)
        seg = llm.segment(numbered)
        all_items = []
        src_lines = numbered.splitlines()
        for t in seg.topics:
            if t.type != "agenda":
                continue
            seg_text = "\n".join(src_lines[t.line_start:t.line_end + 1])
            ext = llm.extract(t.title, seg_text, t.line_start, t.line_end,
                              meeting_date=row["created_at"][:10])
            all_items.extend(i.model_dump() for i in ext.items)
        q = llm.filter_and_summarize(json.dumps(all_items, ensure_ascii=False))

        report_md = _render_report(row["title"], q)
        _set_status(meeting_id, "done",
                    report_md=report_md,
                    executive_summary=q.executive_summary,
                    items=[i.model_dump() for i in q.kept_items])

        # --- gizlilik: ses dosyasini sil ---
        sb.storage.from_(BUCKET).remove([audio_path])
        os.remove(local)
    except Exception as e:
        traceback.print_exc()
        _set_status(meeting_id, "error", error_message=str(e)[:500])


def _render_report(title: str, q) -> str:
    out = [f"# {title}", "", "## Yönetici Özeti", q.executive_summary]
    for kind, label in [("decision", "Kararlar"), ("action_item", "Aksiyon Maddeleri"),
                        ("risk", "Riskler"), ("open_question", "Açık Sorular"),
                        ("idea", "Fikirler")]:
        items = [i for i in q.kept_items if i.type == kind]
        if items:
            out += ["", f"## {label}"]
            for i in items:
                owner = f" — {i.owner}" if i.owner else ""
                dl = f" (son: {i.deadline})" if i.deadline else ""
                out.append(f"- {i.text}{owner}{dl}")
    return "\n".join(out)


@app.post("/process", status_code=202)
def process(req: ProcessReq, bg: BackgroundTasks,
            authorization: str | None = Header(default=None)):
    uid = _user_id_from_jwt(authorization)
    row = sb.table("meetings").select("user_id,status").eq("id", req.meeting_id).single().execute().data
    if not row or row["user_id"] != uid:
        raise HTTPException(404, "Toplantı bulunamadı")
    if row["status"] != "uploaded":
        raise HTTPException(409, f"Beklenmeyen durum: {row['status']}")
    bg.add_task(run_pipeline, req.meeting_id)
    return {"ok": True, "meeting_id": req.meeting_id}


@app.get("/healthz")
def healthz():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
