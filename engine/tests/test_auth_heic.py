from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tshulai import main
from tshulai.auth import AuthError, verify
from tshulai.config import AuthConfig

CFG = AuthConfig(enabled=True, google_client_ids=["web-client", "ios-client"], family={"Grandson@Gmail.com": "阿融"})


@pytest.fixture
def fake_google(monkeypatch):
    """模擬 Google 的 ID token 驗簽：token 字串就是 'email|audience|verified'。"""
    from google.oauth2 import id_token

    def verify_oauth2_token(token, request, audience=None):
        email, aud, verified = token.split("|")
        if aud != audience:
            raise ValueError("Token has wrong audience")
        return {"email": email, "email_verified": verified == "1", "aud": aud}

    monkeypatch.setattr(id_token, "verify_oauth2_token", verify_oauth2_token)


def test_family_member_accepted_any_client(fake_google):
    assert verify("grandson@gmail.com|ios-client|1", CFG).called == "阿融"   # email 大小寫不敏感
    assert verify("grandson@gmail.com|web-client|1", CFG).called == "阿融"


@pytest.mark.parametrize("token,why", [
    (None, "需要登入"),
    ("stranger@gmail.com|web-client|1", "不在家人名單"),
    ("grandson@gmail.com|other-app|1", "無效"),
    ("grandson@gmail.com|web-client|0", "尚未驗證"),
])
def test_rejected(fake_google, token, why):
    with pytest.raises(AuthError, match=why):
        verify(token, CFG)


def test_http_and_ws_enforce_auth(fake_google, isolated_data):
    isolated_data.mkdir(parents=True, exist_ok=True)
    (isolated_data / "config.yaml").write_text(
        "geocoder: none\nauth:\n  enabled: true\n  google_client_ids: [web-client]\n  family: {grandson@gmail.com: 阿融}\n",
        encoding="utf-8")
    good = "grandson@gmail.com|web-client|1"
    with TestClient(main.app) as client:
        assert client.get("/me").status_code == 401
        assert client.get("/me", headers={"Authorization": "Bearer stranger@gmail.com|web-client|1"}).status_code == 401
        me = client.get("/me", headers={"Authorization": f"Bearer {good}"}).json()
        assert me["called"] == "阿融" and me["frame_key"]
        assert client.get(f"/trips?key={me['frame_key']}").status_code == 200    # 看板免登入
        with client.websocket_connect(f"/ws?token={good}") as ws:
            assert ws.receive_json()["member"] == "阿融"
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws") as ws:
                ws.receive_json()


def test_heic_gps(tmp_path: Path):
    """iPhone 的 HEIC：pillow-heif 讀得到拍攝時間與 GPS。"""
    pillow_heif = pytest.importorskip("pillow_heif")
    from PIL import Image

    from helpers import make_photo
    from tshulai.trips import read_photo_meta

    jpg = make_photo(tmp_path / "a.jpg", datetime(2026, 10, 12, 15, 30), 25.17, 121.44)
    with Image.open(jpg) as im:
        exif = im.info["exif"]
        heif = pillow_heif.from_pillow(im)
        heif.info["exif"] = exif
        heif.save(tmp_path / "阿融_IMG_1.HEIC", quality=80)
    m = read_photo_meta(tmp_path / "阿融_IMG_1.HEIC")
    assert m.taken_at == datetime(2026, 10, 12, 15, 30)
    assert abs(m.lat - 25.17) < 0.01 and abs(m.lng - 121.44) < 0.01
