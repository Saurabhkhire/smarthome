"""FastAPI app: HTTP + WebSocket chat, health, listings, session reset."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from agent import clear_session, run_agent
from db.database import SessionLocal, init_db
from db.models import Listing
from db.queries import listing_to_dict
from schemas import ChatRequest, ChatResponse

init_db()

STATIC = Path(__file__).resolve().parent / "static"
STATIC.mkdir(exist_ok=True)
app = FastAPI(title="Real Estate Chatbot API")
app.mount("/assets", StaticFiles(directory=str(STATIC)), name="assets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    index_path = STATIC / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    return {"app": "API", "docs": "/docs", "chat": "POST /chat"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/smtp")
def health_smtp():
    """Debug: Resend + SMTP flags (no secrets)."""
    import config as cfg

    resend = bool(cfg.RESEND_API_KEY)
    smtp = bool(cfg.SMTP_USER and cfg.SMTP_PASS)
    return {
        "email_ready": resend or smtp,
        "resend_ready": resend,
        "smtp_ready": smtp,
        "smtp_user_set": bool(cfg.SMTP_USER),
        "smtp_pass_set": bool(cfg.SMTP_PASS),
        "resend_from": (cfg.RESEND_FROM or "")[:48] + ("…" if len(cfg.RESEND_FROM or "") > 48 else ""),
        "env_file_checked": str(Path(__file__).resolve().parent / ".env"),
    }


@app.get("/listings")
def listings():
    db = SessionLocal()
    try:
        rows = list(db.scalars(select(Listing)).all())
        return [listing_to_dict(r) for r in rows]
    finally:
        db.close()


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        return run_agent(req.message, req.session_id, req.lang)
    except Exception as e:
        return ChatResponse(
            reply=f"Request failed: {str(e)[:200]}. Check OPENAI_API_KEY in .env and run: pip install -r requirements.txt",
            listings=[],
            type="chat",
            lang=req.lang or "en",
            session_id=req.session_id,
        )


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    clear_session(session_id)
    return {"ok": True, "session_id": session_id}


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
                req = ChatRequest(**data)
            except Exception:
                await ws.send_json(
                    ChatResponse(
                        reply="Invalid request JSON.",
                        listings=[],
                        type="chat",
                        lang="en",
                        session_id="default",
                    ).model_dump()
                )
                continue
            try:
                resp = run_agent(req.message, req.session_id, req.lang)
            except Exception as e:
                resp = ChatResponse(
                    reply=str(e)[:200],
                    listings=[],
                    type="chat",
                    lang=req.lang or "en",
                    session_id=req.session_id,
                )
            await ws.send_json(resp.model_dump())
    except WebSocketDisconnect:
        pass
