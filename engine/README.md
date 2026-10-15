# tshulai-engine

Persona Engine。跑在家用主機，手機透過 Tailscale 連進來。

```bash
cd engine
uv sync --extra claude --extra dev
cp ../spec/examples/persona.example.yaml ../data/persona.yaml   # 填你家人的資料
uv run tshulai-engine                                           # ws://localhost:8765/ws
uv run pytest
```

目前狀態：骨架。有的東西：

- `persona/`：人格卡載入與 schema 驗證、system prompt 組裝
- `memory/`：SQLite 記憶庫 schema 與基本讀寫（向量索引待接 sqlite-vec）
- `scene/`：scene YAML 載入與狀態機
- `llm/`：LLM adapter 介面，附 Claude 與 echo（測試用）實作
- `main.py`：FastAPI + WebSocket，事件進、回覆出

還沒有的：語音管線、影像管線、plugin host、生活模擬器。這些在 docs/architecture.md 有設計，照順序補。
