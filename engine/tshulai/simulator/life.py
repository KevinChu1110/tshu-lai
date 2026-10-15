"""生活模擬器：讓她每天「發生事情」，成為主動開口的話題。

事件來源三種，依可信度排：
1. 真的：家人的旅行足跡、給未來的留言日期、節日、阿公忌日（人格卡 dates）
2. 半真的：plugin 提供的天氣、節目表、廟會
3. 編的：依作息表在合理範圍內產生的小事（菜市場遇到誰），受人格卡約束

編的事件只用人格卡和記憶裡已經存在的人與地點，不發明新的家族成員或重大事件。
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime

from ..memory import MemoryStore
from ..persona import PersonaCard

# 農曆節日要查表，這裡先放國曆固定的。之後由 calendar plugin 補農曆。
SOLAR_FESTIVALS = {
    (1, 1): "元旦", (2, 28): "和平紀念日", (4, 4): "兒童節", (5, 1): "勞動節",
    (10, 10): "國慶日", (12, 25): "聖誕節",
}

SMALL_THINGS = [
    "去{place}的時陣拄著{neighbor}，講真久的話",
    "{tv}今仔日演甲足氣人",
    "手機的 LINE 毋知按怎，貼圖揣無",
    "今仔日膝頭仔有較疼",
    "煮{food}，煮傷濟食袂了",
    "門口的花開矣",
]


class LifeSimulator:
    def __init__(self, persona: PersonaCard, memory: MemoryStore):
        self.persona = persona
        self.memory = memory

    def _rng(self, day: date) -> random.Random:
        # 同一天結果固定，重啟引擎不會換一套故事
        seed = int(hashlib.sha256(f"{self.persona['id']}:{day.isoformat()}".encode()).hexdigest()[:8], 16)
        return random.Random(seed)

    def generate(self, day: date | None = None, *, trips_facts: list[str] | None = None) -> list[str]:
        """產生並寫入當天事件。已經產生過就直接回傳。"""
        day = day or date.today()
        existing = self.memory.todays_events(day.isoformat(), unmentioned_only=False)
        if existing:
            return existing
        events: list[tuple[str, str]] = []

        for fact in trips_facts or []:
            events.append((f"孫仔有傳相片來：{fact}", "trips"))
        fest = SOLAR_FESTIVALS.get((day.month, day.day))
        if fest:
            events.append((f"今仔日是{fest}", "calendar"))
        for d in self.persona.get("dates", []):
            md = d.get("date", "")[5:]
            if md == day.strftime("%m-%d"):
                events.append((d["label"], "persona.dates"))

        rng = self._rng(day)
        likes = self.persona.get("likes", {})
        routine = self.persona.get("routine", [])
        fill = {
            "place": next((r.get("place") for r in routine if r.get("place") and "市" in r.get("place", "")), "菜市仔"),
            "neighbor": rng.choice(self.persona.get("neighbors", ["厝邊"])),
            "tv": rng.choice(likes.get("tv", ["八點檔"])),
            "food": rng.choice(likes.get("food", ["飯"])),
        }
        for tmpl in rng.sample(SMALL_THINGS, k=2):
            events.append((tmpl.format(**fill), "simulator"))

        for text, source in events:
            self.memory.add_life_event(day.isoformat(), text, source)
        return [t for t, _ in events]

    def phone_trouble_due(self, now: datetime | None = None) -> bool:
        """一週大概一次，下午讓她拿手機來問問題（觸發 phone_help scene）。"""
        now = now or datetime.now()
        return now.hour in (14, 15) and self._rng(now.date()).random() < 0.15
