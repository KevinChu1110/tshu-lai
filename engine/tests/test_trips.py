from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from helpers import make_photo
from tshulai import main
from tshulai.trips import NullGeocoder, group_trips, read_photo_meta, scan_trips
from tshulai.trips.geocode import Geocoder


class FakeGeo(Geocoder):
    def place(self, lat, lng):
        return "新北市淡水區" if lat > 25 else "臺南市安平區"


def test_exif_gps_read(tmp_path: Path):
    p = make_photo(tmp_path / "阿融_a.jpg", datetime(2026, 10, 12, 15, 0), 25.17, 121.44)
    m = read_photo_meta(p)
    assert m.taken_at == datetime(2026, 10, 12, 15, 0)
    assert abs(m.lat - 25.17) < 0.01 and abs(m.lng - 121.44) < 0.01
    assert m.uploader == "阿融"


def test_group_by_person_and_gap(tmp_path: Path):
    d = tmp_path / "trips"
    make_photo(d / "阿融_1.jpg", datetime(2026, 10, 11, 10), 25.17, 121.44)
    make_photo(d / "阿融_2.jpg", datetime(2026, 10, 12, 16), 25.17, 121.44)
    make_photo(d / "阿融_3.jpg", datetime(2026, 9, 1, 9), 23.0, 120.16)
    make_photo(d / "阿舅_1.jpg", datetime(2026, 10, 12, 9), 23.0, 120.16)
    trips = scan_trips(d, FakeGeo())
    assert len(trips) == 3
    tamsui = next(t for t in trips if t.who == "阿融" and t.places == ["新北市淡水區"])
    assert tamsui.start.isoformat() == "2026-10-11" and tamsui.end.isoformat() == "2026-10-12"
    assert "淡水" in tamsui.as_fact()
    assert trips[-1].start.isoformat() == "2026-09-01"  # 新的在前


def test_no_gps_still_groups(tmp_path: Path):
    p = make_photo(tmp_path / "x.jpg", datetime(2026, 10, 1, 9))
    trips = group_trips([read_photo_meta(p)], NullGeocoder())
    assert len(trips) == 1 and trips[0].places == []


def test_upload_then_frame(isolated_data, monkeypatch):
    monkeypatch.setenv("TSHULAI_DATA", str(isolated_data))
    (isolated_data).mkdir(parents=True, exist_ok=True)
    (isolated_data / "config.yaml").write_text("geocoder: none\n", encoding="utf-8")
    photo = make_photo(isolated_data.parent / "src" / "IMG_1.jpg", datetime(2026, 10, 12, 10), 25.17, 121.44)
    with TestClient(main.app) as client:
        r = client.post("/trips/upload", files={"files": ("IMG_1.jpg", photo.read_bytes(), "image/jpeg")})
        assert r.status_code == 200 and r.json()["saved"]
        key = main.engine.frame_key
        assert client.get("/frame?key=wrong").status_code == 403
        assert "阿嬤看板" in client.get(f"/frame?key={key}").text
        trips = client.get(f"/trips?key={key}").json()
        assert len(trips) == 1
        img = client.get(f"/media/{trips[0]['photos'][0]}?key={key}")
        assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
        assert client.get(f"/media/../config.yaml?key={key}").status_code == 404
        # 數位阿嬤記得這趟
        assert any("𨑨迌" in f for f in main.engine.memory.recent_facts())


def test_short_place_names():
    from tshulai.trips.geocode import short_place

    assert short_place({"city": "新北市", "suburb": "淡水區", "town": "淡水區", "country_code": "tw"}) == "淡水"
    assert short_place({"city": "臺南市", "suburb": "安平區", "village": "上鯤鯓", "country_code": "tw"}) == "安平"
    assert short_place({"county": "花蓮縣", "country_code": "tw"}) == "花蓮"
    assert short_place({"city": "大阪市", "country_code": "jp"}) == "大阪市"
