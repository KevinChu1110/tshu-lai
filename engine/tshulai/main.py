"""FastAPI + WebSocket。Client 送事件與文字進來，Engine 回文字串流。

訊息格式（JSON）：
  client -> engine
    {"type": "event", "name": "geofence.enter:home"}
    {"type": "say", "text": "阿嬤我轉來矣"}
  engine -> client
    {"type": "scene", "id": "homecoming", "name": "進門"}
    {"type": "text", "delta": "轉來矣喔，"}
    {"type": "text_end"}
語音與影像之後掛在同一條 socket 上，用 type 區分。
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .llm import Turn, get_llm
from .memory import MemoryStore
from .persona import build_system_prompt, load_persona
from .scene import SceneMachine, load_scenes

DATA = Path(os.environ.get("TSHULAI_DATA", Path(__file__).resolve().parents[2] / "data"))

class Engine:
    def __init__(self):
        persona_path = DATA / "persona.yaml"
        if not persona_path.exists():
            persona_path = Path(__file__).resolve().parents[2] / "spec" / "examples" / "persona.example.yaml"
        self.persona = load_persona(persona_path)
        self.memory = MemoryStore(DATA / "persona.db")
        self.scenes = SceneMachine(load_scenes())
        self.llm = get_llm(os.environ.get("TSHULAI_LLM", "echo"))
        self.user_name = os.environ.get("TSHULAI_USER", "使用者")

    def system_prompt(self, user_text: str) -> str:
        return build_system_prompt(
            self.persona,
            scene=f"{self.scenes.current.name}：{self.scenes.current.description}",
            today_events=self.memory.todays_events(date.today().isoformat()),
            memories=self.memory.search_stories(user_text) + self.memory.recent_facts(5),
            user_name=self.user_name,
        )


engine: Engine | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global engine
    engine = Engine()
    yield


app = FastAPI(title="厝內 Persona Engine", lifespan=lifespan)


@app.get("/health")
def health():
    assert engine
    return {"persona": engine.persona.display_name, "scene": engine.scenes.current.id, "llm": type(engine.llm).__name__}


@app.websocket("/ws")
async def ws(sock: WebSocket):
    assert engine
    await sock.accept()
    await sock.send_json({"type": "scene", "id": engine.scenes.current.id, "name": engine.scenes.current.name})
    try:
        while True:
            msg = await sock.receive_json()
            if msg.get("type") == "event":
                new = engine.scenes.on_event(msg["name"])
                if new:
                    await sock.send_json({"type": "scene", "id": new.id, "name": new.name})
            elif msg.get("type") == "say":
                text = msg["text"]
                history = [Turn(r, t) for r, t in engine.memory.recent_turns()]
                engine.memory.log_turn("user", text, engine.scenes.current.id)
                reply = []
                async for delta in engine.llm.stream(engine.system_prompt(text), history, text):
                    reply.append(delta)
                    await sock.send_json({"type": "text", "delta": delta})
                await sock.send_json({"type": "text_end"})
                engine.memory.log_turn("persona", "".join(reply), engine.scenes.current.id)
    except WebSocketDisconnect:
        pass


def run():
    uvicorn.run("tshulai.main:app", host=os.environ.get("TSHULAI_HOST", "127.0.0.1"), port=int(os.environ.get("TSHULAI_PORT", "8765")))


if __name__ == "__main__":
    run()
