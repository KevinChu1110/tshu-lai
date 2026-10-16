"""厝內 Persona Engine：HTTP + WebSocket。

WebSocket /ws（第一則訊息 {"type":"auth","token":"<Google ID token>"}，auth 關閉時可省略）
  client -> engine
    {"type": "event", "name": "geofence.enter:home"}
    {"type": "say", "text": "阿嬤我轉來矣"}
    {"type": "voice", "tts": true}           之後的回覆都附語音
  engine -> client
    {"type": "hello", "member": "阿融", "scene": {...}}
    {"type": "scene", "id": "homecoming", "name": "進門"}
    {"type": "text", "delta": "轉來矣喔，"}
    {"type": "sentence", "text": "轉來矣喔，食飽未？", "audio": "/tts/<key>"}   開了語音才有
    {"type": "text_end"}
    {"type": "future", "id": 3, "audio": "/media/future/..."}               給未來的留言到期

HTTP（家人登入後才能用，Authorization: Bearer <Google ID token>）
  GET  /health                 GET  /trips              GET /media/{path}
  POST /trips/upload           GET  /frame（阿嬤看板網頁，?key= 免登入，給平板）
  GET  /future/manual          POST /future/{id}/played
  GET  /poses                  POST /photo/composite（合照好版）
  POST /stt                    GET  /tts/{key}
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
import secrets
from contextlib import asynccontextmanager, suppress
from datetime import date
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response

from .auth import AuthError, Member, verify
from .config import Config, load_config
from .future import parse_future_dir
from .llm import Turn, get_llm
from .memory import MemoryStore
from .persona import build_system_prompt, load_persona
from .plugins import PluginHost, load_manifests
from .scene import SceneMachine, load_scenes
from .simulator import LifeSimulator
from .storage import ensure_local_layout
from .trips import NominatimGeocoder, NullGeocoder, scan_trips
from .voice import SentenceSplitter, get_stt, get_tts

log = logging.getLogger("tshulai")
REPO = Path(__file__).resolve().parents[2]
WEB = Path(__file__).resolve().parent / "web"


class Engine:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        d = cfg.data_dir
        d.mkdir(parents=True, exist_ok=True)
        persona_path = d / "persona.yaml"
        if not persona_path.exists():
            persona_path = REPO / "spec" / "examples" / "persona.example.yaml"
        self.persona = load_persona(persona_path)
        self.memory = MemoryStore(d / "persona.db", vectors=cfg.vector_memory and cfg.llm != "echo")
        self.scenes = SceneMachine(load_scenes())
        self.llm = get_llm(cfg.llm)
        self.simulator = LifeSimulator(self.persona, self.memory)
        self.geocoder = (NominatimGeocoder(d / "geocode_cache.json", cfg.geocoder_contact)
                         if cfg.geocoder == "nominatim" else NullGeocoder())
        for root in cfg.media_roots[1:]:
            ensure_local_layout(root)
        self.tts = get_tts(cfg.tts, url=cfg.tts_url, ref_audio=self._media(cfg.tts_ref) if cfg.tts_ref else None,
                           ref_text=cfg.tts_ref_text, translator_url=cfg.translator_url, cache_dir=d / "tts_cache",
                           persona_id=self.persona["id"])
        self._stt = None
        self.tts_store: dict[str, bytes] = {}
        self.frame_key = self._frame_key()
        home = self.persona.get("home") or {}
        env = {"TSHULAI_HOME_LAT": str(home["lat"]), "TSHULAI_HOME_LNG": str(home["lng"])} if "lat" in home else {}
        tv = d / "plugins" / "tv-schedule.yaml"
        if tv.exists():
            env["TSHULAI_TV_SCHEDULE"] = str(tv)
        self.plugins = PluginHost(load_manifests([REPO / "plugins", d / "plugins"], cfg.plugins or []), env)
        self.connections: dict[WebSocket, dict] = {}   # sock -> {"who": Member, "voice": bool}

    def _frame_key(self) -> str:
        p = self.cfg.data_dir / "frame_key.txt"
        if not p.exists():
            p.write_text(secrets.token_urlsafe(16))
        return p.read_text().strip()

    def _media(self, rel: str) -> Path | None:
        """在各素材根目錄找檔案，不允許跳出根目錄。"""
        for root in self.cfg.media_roots:
            p = (root / rel).resolve()
            if p.is_relative_to(root.resolve()) and p.is_file():
                return p
        return None

    @property
    def stt(self):
        if self._stt is None:
            self._stt = get_stt(self.cfg.stt)
        return self._stt

    # --- 背景工作 -----------------------------------------------------
    def refresh_media(self) -> None:
        """掃旅行照片、給未來的留言。Drive 同步完、或有人上傳後呼叫。"""
        trips = []
        for root in self.cfg.media_roots:
            for t in scan_trips(root / "trips", self.geocoder):
                trips.append(t.to_json(root))
        new = self.memory.upsert_trips(trips)
        for t in new:
            self.memory.add_fact(f"{t['who'] or '孫仔'}最近去{'、'.join(t['places'][:2]) or '外口'}𨑨迌，{t['start']}")
        birthdays = {p["called"]: p["birthday"] for p in self.persona.get("people", []) if p.get("birthday")}
        for root in self.cfg.media_roots:
            self.memory.sync_future_messages(parse_future_dir(root, birthdays))

    async def daily(self) -> None:
        topics = []
        with suppress(Exception):
            topics = await self.plugins.topics()
        trip_facts = [f"{t['title']}（{t['start']}）" for t in self.memory.recent_trips(3) if t["end"] >= date.today().replace(day=1).isoformat()]
        self.simulator.generate(trips_facts=trip_facts)
        for t in topics:
            self.memory.add_life_event(date.today().isoformat(), t, "plugin")

    def quiet_now(self) -> bool:
        from datetime import datetime

        start, end = self.cfg.wellbeing.quiet_hours
        h = datetime.now().hour
        return (h >= start or h < end) if start > end else (start <= h < end)

    def system_prompt(self, user_text: str, member: Member, remind_rest: bool = False) -> str:
        trips = self.memory.recent_trips(3)
        memories = self.memory.search_stories(user_text) + self.memory.recent_facts(5)
        memories += [f"{t['title']}，{t['start']}" for t in trips]
        return build_system_prompt(
            self.persona,
            scene=f"{self.scenes.current.name}：{self.scenes.current.description}",
            today_events=self.memory.todays_events(date.today().isoformat()),
            memories=memories,
            user_name=member.called or self.cfg.user_name,
            farewell=self.cfg.wellbeing.farewell,
            remind_rest=remind_rest,
        )

    def speak(self, text: str) -> str | None:
        try:
            audio = self.tts.synth(text)
        except Exception as e:
            log.warning("TTS 失敗：%s", e)
            return None
        if not audio:
            return None
        key = hashlib.sha1(text.encode()).hexdigest()[:16]
        self.tts_store[key] = audio
        if len(self.tts_store) > 200:
            self.tts_store.pop(next(iter(self.tts_store)))
        return f"/tts/{key}"


engine: Engine | None = None


async def _drive_loop(e: Engine) -> None:
    from .storage.drive import DriveMirror, service_account_creds

    creds = service_account_creds(e.cfg.data_dir / e.cfg.drive.service_account)
    mirror = DriveMirror(creds, e.cfg.drive.folder_id, e.cfg.data_dir / "drive")
    missing = await asyncio.to_thread(mirror.missing_folders)
    if missing:
        log.warning("Drive 資料夾缺少：%s（見 docs/google-drive.md）", "、".join(missing))
    while True:
        try:
            changed = await asyncio.to_thread(mirror.sync)
            if changed:
                await asyncio.to_thread(e.refresh_media)
        except Exception as ex:
            log.warning("Drive 同步失敗：%s", ex)
        await asyncio.sleep(e.cfg.drive.poll_seconds)


# plugin 事件 → 阿嬤主動開口的提示（括號是給 LLM 的舞台指示，不會念出來）
PROACTIVE = {
    "weather.rain_soon": "（等一下會落雨，提醒對方出門愛紮雨傘。）",
    "festival.today": "（今天是節日，照你的習慣跟對方講今天要做什麼。）",
    "tv.program_started": "（你常看的節目開始了，叫對方一起來看。）",
}


async def handle_event(e: Engine, name: str) -> None:
    """plugin 或 app 來的事件：換 scene，必要時對所有連線中的家人主動開口。"""
    new = e.scenes.on_event(name)
    for sock, c in list(e.connections.items()):
        with suppress(Exception):
            if new:
                await sock.send_json({"type": "scene", "id": new.id, "name": new.name})
            if name in PROACTIVE and not e.cfg.wellbeing.farewell and not e.quiet_now():
                await _reply(sock, c["who"], PROACTIVE[name], c["voice"], log_user=False)


async def _plugin_loop(e: Engine) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            for name in await e.plugins.poll_events():
                if e.memory.first_time_today(date.today().isoformat(), name):
                    await handle_event(e, name)
        except Exception as ex:
            log.warning("plugin 事件輪詢失敗：%s", ex)


async def _daily_loop(e: Engine) -> None:
    last = None
    while True:
        if date.today() != last:
            with suppress(Exception):
                await e.daily()
            last = date.today()
        await asyncio.sleep(600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global engine
    engine = Engine(load_config())
    await asyncio.to_thread(engine.refresh_media)
    tasks = [asyncio.create_task(_daily_loop(engine))]
    if engine.cfg.drive.enabled:
        tasks.append(asyncio.create_task(_drive_loop(engine)))
    if engine.plugins.plugins:
        await engine.plugins.start()
        tasks.append(asyncio.create_task(_plugin_loop(engine)))
    log.info("阿嬤看板：/frame?key=%s", engine.frame_key)
    yield
    for t in tasks:
        t.cancel()
    with suppress(Exception):
        await engine.plugins.stop()


app = FastAPI(title="厝內 Persona Engine", lifespan=lifespan)
# Flutter 網頁版若從別的網址開也能連；身分靠 Bearer token，不靠 cookie
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
APP_WEB = REPO / "app" / "build" / "web"


def member(authorization: str | None = Header(None)) -> Member:
    assert engine
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    try:
        return verify(token, engine.cfg.auth)
    except AuthError as e:
        raise HTTPException(401, str(e)) from e


def frame_or_member(key: str | None = Query(None), authorization: str | None = Header(None)) -> Member:
    assert engine
    if key and secrets.compare_digest(key, engine.frame_key):
        return Member("frame", "阿嬤看板")
    return member(authorization)


@app.get("/health")
def health():
    assert engine
    return {"persona": engine.persona.display_name, "scene": engine.scenes.current.id,
            "llm": type(engine.llm).__name__, "tts": type(engine.tts).__name__,
            "drive": engine.cfg.drive.enabled, "auth": engine.cfg.auth.enabled,
            "plugins": list(engine.plugins.plugins)}


@app.get("/me")
def me(who: Member = Depends(member)):
    """登入後的家人資訊。app 用 home 註冊 geofence，frame_key 給家人設定阿嬤看板。"""
    assert engine
    return {"email": who.email, "called": who.called, "persona": engine.persona.display_name,
            "home": engine.persona.get("home"), "frame_key": engine.frame_key}


@app.post("/events")
def post_event(body: dict, who: Member = Depends(member)):
    """app 在背景（geofence）時用 HTTP 報事件；下次連線時阿嬤就知道你回來過。"""
    assert engine
    name = str(body.get("name", ""))[:64]
    if name.startswith("geofence.enter"):
        engine.memory.add_fact(f"{who.called or '孫仔'}{date.today().strftime('%-m月%-d日')}有轉來厝")
    engine.scenes.on_event(name)
    return {"scene": engine.scenes.current.id}


@app.get("/wellbeing")
def wellbeing(who: Member = Depends(member)):
    """今天跟阿嬤講了多久。app 設定頁顯示，讓家人自己看得到。"""
    assert engine
    row = engine.memory.conn.execute("SELECT seconds FROM usage WHERE day=? AND member=?",
                                     (date.today().isoformat(), who.email)).fetchone()
    return {"minutes_today": round((row[0] if row else 0) / 60), "daily_minutes": engine.cfg.wellbeing.daily_minutes,
            "farewell": engine.cfg.wellbeing.farewell}


@app.get("/trips")
def trips(n: int = 20, who: Member = Depends(frame_or_member)):
    assert engine
    return engine.memory.recent_trips(n)


@app.post("/trips/upload")
async def trips_upload(files: list[UploadFile] = File(...), who: Member = Depends(member)):
    """app 直接上傳旅行照片。存在家用主機 uploads/trips/，檔名前綴是上傳者的稱呼。"""
    assert engine
    dst_dir = engine.cfg.data_dir / "uploads" / "trips"
    dst_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        name = Path(f.filename or "photo.jpg").name
        prefix = who.called or who.email.split("@")[0]
        dst = dst_dir / f"{prefix}_{name}"
        dst.write_bytes(await f.read())
        saved.append(dst.name)
    await asyncio.to_thread(engine.refresh_media)
    return {"saved": saved, "trips": engine.memory.recent_trips(3)}


@app.get("/media/{path:path}")
def media(path: str, who: Member = Depends(frame_or_member)):
    assert engine
    p = engine._media(path)
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type=mimetypes.guess_type(p.name)[0])


@app.get("/frame", response_class=HTMLResponse)
def frame(key: str = Query(...)):
    assert engine
    if not secrets.compare_digest(key, engine.frame_key):
        raise HTTPException(403)
    return (WEB / "frame.html").read_text(encoding="utf-8")


@app.get("/future/manual")
def future_manual(who: Member = Depends(member)):
    assert engine
    return engine.memory.manual_future_messages(who.called or None)


@app.post("/future/{msg_id}/played")
def future_played(msg_id: int, who: Member = Depends(member)):
    assert engine
    engine.memory.mark_played(msg_id)
    return {"ok": True}


@app.get("/poses")
def poses(who: Member = Depends(member)):
    assert engine
    from .vision.poses import PoseLibrary

    return PoseLibrary(engine.cfg.data_dir / "poses").list()


@app.get("/poses/{name}")
def pose_png(name: str, who: Member = Depends(member)):
    assert engine
    p = (engine.cfg.data_dir / "poses" / Path(name).name)
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")


@app.post("/photo/composite")
async def photo_composite(photo: UploadFile = File(...), pose: str = Form(...), position: str = Form("center"),
                          who: Member = Depends(member)):
    """合照好版：ComfyUI + Qwen-Image-Edit。回傳標記過 AI 的 JPEG。"""
    assert engine
    if not engine.cfg.comfy_url:
        raise HTTPException(501, "沒有設定 comfy_url，只能用 app 內的快版合照")
    if position not in ("left", "center", "right"):
        raise HTTPException(400, "position 要是 left / center / right")
    import tempfile

    from .vision.comfy import ComfyClient, insert_person
    from .vision.label import mark_ai_image

    ref = engine.cfg.data_dir / "poses" / Path(pose).name
    if not ref.is_file():
        raise HTTPException(404, "姿勢庫沒有這張")
    with tempfile.NamedTemporaryFile(suffix=Path(photo.filename or "a.jpg").suffix) as tmp:
        tmp.write(await photo.read())
        tmp.flush()
        out = await asyncio.to_thread(insert_person, ComfyClient(engine.cfg.comfy_url), Path(tmp.name), ref, position)
    engine.memory.add_fact(f"{who.called or '孫仔'}佮阿嬤翕一張合照")
    return Response(mark_ai_image(out, composite=True), media_type="image/jpeg")


@app.post("/stt")
async def stt(audio: UploadFile = File(...), who: Member = Depends(member)):
    assert engine
    try:
        text = await asyncio.to_thread(engine.stt.transcribe, await audio.read())
    except RuntimeError as e:
        raise HTTPException(501, str(e)) from e
    return {"text": text}


@app.get("/tts/{key}")
def tts_audio(key: str):
    assert engine
    audio = engine.tts_store.get(key)
    if audio is None:
        raise HTTPException(404)
    return Response(audio, media_type=engine.tts.media_type)


@app.websocket("/ws")
async def ws(sock: WebSocket):
    """登入憑證放第一則訊息 {"type":"auth","token":...}，不放網址（網址會進伺服器紀錄）。"""
    assert engine
    await sock.accept()
    token = None
    if engine.cfg.auth.enabled:
        try:
            first = await asyncio.wait_for(sock.receive_json(), timeout=15)
            token = first.get("token") if first.get("type") == "auth" else None
        except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
            pass
    try:
        who = verify(token, engine.cfg.auth)
    except AuthError as e:
        await sock.send_json({"type": "error", "code": 401, "message": str(e)})
        await sock.close(code=4401)
        return
    voice = False
    conn = engine.connections[sock] = {"who": who, "voice": False}
    import time

    opened = time.monotonic()
    cur = engine.scenes.current
    await sock.send_json({"type": "hello", "member": who.called, "persona": engine.persona.display_name,
                          "scene": {"id": cur.id, "name": cur.name}})
    for m in engine.memory.due_future_messages(date.today().isoformat(), who.called or None):
        await sock.send_json({"type": "future", "id": m["id"], "audio": f"/media/{m['path']}"})
    try:
        while True:
            msg = await sock.receive_json()
            kind = msg.get("type")
            if kind == "voice":
                voice = conn["voice"] = bool(msg.get("tts"))
            elif kind == "event":
                new = engine.scenes.on_event(msg["name"])
                if new:
                    await sock.send_json({"type": "scene", "id": new.id, "name": new.name})
                    if new.id in ("homecoming", "photo"):
                        await _reply(sock, who, f"（{new.description}請你先開口。）", voice, log_user=False)
            elif kind == "say":
                await _reply(sock, who, msg["text"], voice)
    except WebSocketDisconnect:
        pass
    finally:
        engine.connections.pop(sock, None)
        engine.memory.add_usage(date.today().isoformat(), who.email, time.monotonic() - opened)


async def _reply(sock: WebSocket, who: Member, text: str, voice: bool, log_user: bool = True) -> None:
    assert engine
    history = [Turn(r, t) for r, t in engine.memory.recent_turns()]
    if log_user:
        engine.memory.log_turn("user", text, engine.scenes.current.id)
    splitter = SentenceSplitter()
    reply = []

    async def send_sentences(sents: list[str]):
        for s in sents:
            audio = await asyncio.to_thread(engine.speak, s) if voice else None
            await sock.send_json({"type": "sentence", "text": s, "audio": audio})

    import time

    conn = engine.connections.get(sock)
    remind = False
    if conn is not None and log_user:
        # 把這次連線到現在的時間先算進去，判斷今天是不是講太久
        engine.memory.add_usage(date.today().isoformat(), who.email, 0)
        remind = engine.memory.should_remind(date.today().isoformat(), who.email,
                                             engine.cfg.wellbeing.daily_minutes * 60)
    async for delta in engine.llm.stream(engine.system_prompt(text, who, remind_rest=remind), history, text):
        reply.append(delta)
        await sock.send_json({"type": "text", "delta": delta})
        await send_sentences(splitter.feed(delta))
    await send_sentences(splitter.flush())
    await sock.send_json({"type": "text_end"})
    engine.memory.log_turn("persona", "".join(reply), engine.scenes.current.id)


if APP_WEB.is_dir():
    # 引擎直接提供網頁版 app：家人開 <引擎位址>/app/ 就能用，不用裝
    from fastapi.staticfiles import StaticFiles

    app.mount("/app", StaticFiles(directory=APP_WEB, html=True), name="app")


def run():
    import os

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run("tshulai.main:app", host=os.environ.get("TSHULAI_HOST", "127.0.0.1"),
                port=int(os.environ.get("TSHULAI_PORT", "8765")), access_log=False)


if __name__ == "__main__":
    run()
