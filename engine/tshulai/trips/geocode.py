"""反查地名。預設 OpenStreetMap Nominatim：免費，但使用規範要求每秒最多 1 次、
要帶可識別的 User-Agent 與聯絡方式、結果要快取。這裡全做到。"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


def short_place(a: dict) -> str | None:
    """阿嬤聽得懂的地名：鄉鎮區名，去掉「區」。淡水區 → 淡水，安平區 → 安平；
    鄉鎮找不到才用縣市（臺南市 → 臺南）。國外用城市名。"""
    town = a.get("suburb") or a.get("town") or a.get("city_district") or a.get("district")
    if a.get("country_code", "tw") == "tw":
        if town:
            return town[:-1] if len(town) > 2 and town.endswith("區") else town
        city = a.get("city") or a.get("county") or a.get("state")
        return city[:-1] if city and len(city) > 2 and city.endswith(("市", "縣")) else city
    return a.get("city") or a.get("town") or a.get("state") or a.get("country")


class Geocoder:
    def place(self, lat: float, lng: float) -> str | None:  # pragma: no cover
        raise NotImplementedError


class NullGeocoder(Geocoder):
    def place(self, lat: float, lng: float) -> str | None:
        return None


class NominatimGeocoder(Geocoder):
    URL = "https://nominatim.openstreetmap.org/reverse"

    def __init__(self, cache_file: Path, contact: str = ""):
        self.cache_file = cache_file
        self.cache: dict[str, str | None] = json.loads(cache_file.read_text()) if cache_file.exists() else {}
        self.ua = "tshu-lai/0.1 (+https://github.com/KevinChu1110/tshu-lai" + (f"; {contact}" if contact else "") + ")"
        self._last = 0.0

    def place(self, lat: float, lng: float) -> str | None:
        key = f"v3:{lat:.2f},{lng:.2f}"  # 約 1 公里；只要鄉鎮名，同一區查一次就好
        if key in self.cache:
            return self.cache[key]
        wait = 1.1 - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        q = urllib.parse.urlencode({"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 10, "accept-language": "zh-TW"})
        req = urllib.request.Request(f"{self.URL}?{q}", headers={"User-Agent": self.ua})
        name = None
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            name = short_place(data.get("address", {})) or data.get("name")
        except Exception:
            name = None
        finally:
            self._last = time.monotonic()
        self.cache[key] = name
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        return name
