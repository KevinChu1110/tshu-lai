from datetime import datetime
from pathlib import Path

from PIL import Image


def make_photo(path: Path, when: datetime, lat: float | None = None, lng: float | None = None) -> Path:
    """產生帶 EXIF 時間與 GPS 的測試照片。"""
    im = Image.new("RGB", (64, 48), (200, 120, 60))
    exif = im.getexif()
    exif.get_ifd(0x8769)[0x9003] = when.strftime("%Y:%m:%d %H:%M:%S")
    if lat is not None:
        def dms(v):
            v = abs(v)
            d = int(v)
            m = int((v - d) * 60)
            s = round(((v - d) * 60 - m) * 60, 2)
            return (float(d), float(m), float(s))
        gps = exif.get_ifd(0x8825)
        gps[1] = "N" if lat >= 0 else "S"
        gps[2] = dms(lat)
        gps[3] = "E" if lng >= 0 else "W"
        gps[4] = dms(lng)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", exif=exif)
    return path
