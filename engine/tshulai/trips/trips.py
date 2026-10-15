from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .exif import PHOTO_EXT, PhotoMeta, read_photo_meta
from .geocode import Geocoder


@dataclass
class Trip:
    who: str | None
    start: date
    end: date
    places: list[str] = field(default_factory=list)
    photos: list[Path] = field(default_factory=list)
    lat: float | None = None
    lng: float | None = None

    @property
    def title(self) -> str:
        where = "、".join(self.places[:3]) or "某个所在"
        return f"{self.who or '有人'}去{where}"

    def as_fact(self) -> str:
        when = self.start.strftime("%-m月%-d日") + ("" if self.start == self.end else f"到{self.end.strftime('%-m月%-d日')}")
        return f"{when}{self.title}，翕了{len(self.photos)}張相"

    def to_json(self, root: Path) -> dict:
        return {
            "who": self.who, "start": self.start.isoformat(), "end": self.end.isoformat(),
            "title": self.title, "places": self.places, "lat": self.lat, "lng": self.lng,
            "photos": [str(p.relative_to(root)) for p in self.photos],
        }


def group_trips(metas: list[PhotoMeta], geocoder: Geocoder, gap_days: int = 1) -> list[Trip]:
    """同一個人、日期相連（間隔不超過 gap_days）的照片算同一趟。新的在前。"""
    metas = sorted((m for m in metas if m.taken_at), key=lambda m: (m.uploader or "", m.taken_at))
    trips: list[Trip] = []
    cur: list[PhotoMeta] = []

    def flush():
        if not cur:
            return
        days = [m.taken_at.date() for m in cur]
        places = Counter()
        coords = [(m.lat, m.lng) for m in cur if m.lat is not None]
        # 每趟最多查 5 個點，夠描述去了哪
        step = max(1, len(coords) // 5)
        for lat, lng in coords[::step][:5]:
            name = geocoder.place(lat, lng)
            if name:
                places[name] += 1
        lat = sum(c[0] for c in coords) / len(coords) if coords else None
        lng = sum(c[1] for c in coords) / len(coords) if coords else None
        trips.append(Trip(cur[0].uploader, min(days), max(days), [p for p, _ in places.most_common()],
                          [m.path for m in cur], lat, lng))

    for m in metas:
        if cur and (m.uploader != cur[-1].uploader or m.taken_at.date() - cur[-1].taken_at.date() > timedelta(days=gap_days)):
            flush()
            cur = []
        cur.append(m)
    flush()
    trips.sort(key=lambda t: t.end, reverse=True)
    return trips


def scan_trips(trips_dir: Path, geocoder: Geocoder) -> list[Trip]:
    if not trips_dir.exists():
        return []
    metas = [read_photo_meta(p) for p in sorted(trips_dir.rglob("*")) if p.suffix.lower() in PHOTO_EXT]
    return group_trips(metas, geocoder)
