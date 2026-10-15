from fastapi.testclient import TestClient

from tshulai import main


def _drain(ws):
    deltas = []
    while True:
        m = ws.receive_json()
        if m["type"] == "text_end":
            return "".join(deltas)
        if m["type"] == "text":
            deltas.append(m["delta"])


def test_ws_roundtrip():
    with TestClient(main.app) as client:
        with client.websocket_connect("/ws") as ws:
            hello = ws.receive_json()
            assert hello["type"] == "hello" and hello["persona"] == "阿嬤"
            ws.send_json({"type": "event", "name": "geofence.enter:home"})
            assert ws.receive_json()["id"] == "homecoming"
            _drain(ws)  # 進門時阿嬤會先開口
            ws.send_json({"type": "say", "text": "阿嬤我轉來矣"})
            assert "阿嬤我轉來矣" in _drain(ws)


def test_health_reports_components():
    with TestClient(main.app) as client:
        h = client.get("/health").json()
        assert h["persona"] == "阿嬤" and h["drive"] is False and h["auth"] is False
