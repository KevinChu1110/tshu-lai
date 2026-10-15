from fastapi.testclient import TestClient

from tshulai import main


def test_ws_roundtrip():
    with TestClient(main.app) as client:
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "scene"
            ws.send_json({"type": "event", "name": "geofence.enter:home"})
            assert ws.receive_json()["id"] == "homecoming"
            ws.send_json({"type": "say", "text": "阿嬤我轉來矣"})
            deltas = []
            while True:
                m = ws.receive_json()
                if m["type"] == "text_end":
                    break
                deltas.append(m["delta"])
            assert "阿嬤我轉來矣" in "".join(deltas)
