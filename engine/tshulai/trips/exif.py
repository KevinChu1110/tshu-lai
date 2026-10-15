from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

try:  # iPhone 的 HEIC
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}


@dataclass
class PhotoMeta:
    path: Path
    taken_at: datetime | None
    lat: float | None
    lng: float | None
    uploader: str | None = None   # 檔名前綴「阿融_」或 Drive 擁有者，誰去玩的


def _ratio(v) -> float:
    try:
        return float(v)
    except TypeError:
        num, den = v
        return num / den if den else 0.0


def _dms(values, ref) -> float | None:
    if not values:
        return None
    d, m, s = (_ratio(x) for x in values)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def read_photo_meta(path: Path) -> PhotoMeta:
    taken = lat = lng = None
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            named = {TAGS.get(k, k): v for k, v in exif.items()}
            sub = exif.get_ifd(0x8769)  # Exif IFD，DateTimeOriginal 在這
            named.update({TAGS.get(k, k): v for k, v in sub.items()})
            raw = named.get("DateTimeOriginal") or named.get("DateTime")
            if raw:
                try:
                    taken = datetime.strptime(str(raw).strip("\x00"), "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    pass
            gps_ifd = exif.get_ifd(0x8825)
            if gps_ifd:
                gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
                lat = _dms(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
                lng = _dms(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
    except Exception:
        pass
    if taken is None:
        taken = datetime.fromtimestamp(path.stat().st_mtime)
    uploader = path.name.split("_", 1)[0] if "_" in path.name else None
    return PhotoMeta(path, taken, lat, lng, uploader)
