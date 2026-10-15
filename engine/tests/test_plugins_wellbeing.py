import sys
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tshulai import main
from tshulai.memory import MemoryStore
from tshulai.persona import build_system_prompt, load_persona

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def plugin_path(monkeypatch):
    def add(name):
        monkeypatch.syspath_prepend(str(REPO / "plugins" / name))
    return add


def test_calendar_festivals(plugin_path):
    pytest.importorskip("lunar_python")
    plugin_path("calendar-tw")
    from festivals import festivals_on, topics_for

    assert festivals_on(date(2026, 2, 17))[0][0] == "過年"
    assert festivals_on(date(2026, 2, 16))[0][0] == "除夕"
    assert festivals_on(date(2026, 8, 27))[0][0] == "中元普渡"
    assert festivals_on(date(2026, 9, 25))[0][0] == "中秋"
    assert any(n == "清明" for n, _ in festivals_on(date(2026, 4, 5)))
    assert "後日就是中秋矣" in topics_for(date(2026, 9, 23))


def test_tv_schedule(plugin_path, tmp_path):
    plugin_path("tv-taiwan")
    import schedule as sched

    f = tmp_path / "s.yaml"
    f.write_text("shows:\n  - {name: 八點檔, channel: 民視, weekdays: [1,2,3,4,5], start: '20:00', end: '22:00'}\n", encoding="utf-8")
    shows = sched.load(f)
    fri_8pm = datetime(2026, 10, 16, 20, 1)
    assert sched.events(shows, fri_8pm) == ["tv.program_started"]
    assert sched.events(shows, datetime(2026, 10, 16, 20, 10)) == []
    assert sched.events(shows, datetime(2026, 10, 17, 20, 1)) == []          # 禮拜六沒有
    assert sched.on_air(shows, fri_8pm).name == "八點檔"
    assert "今暗8點民視八點檔" in sched.topics(shows, datetime(2026, 10, 16, 18))[0]


def test_usage_reminder_once(tmp_path):
    m = MemoryStore(tmp_path / "p.db")
    m.add_usage("2026-10-16", "a@x", 50 * 60)
    assert not m.should_remind("2026-10-16", "a@x", 90 * 60)
    m.add_usage("2026-10-16", "a@x", 45 * 60)
    assert m.should_remind("2026-10-16", "a@x", 90 * 60)
    assert not m.should_remind("2026-10-16", "a@x", 90 * 60)   # 一天只提醒一次


def test_event_dedupe(tmp_path):
    m = MemoryStore(tmp_path / "p.db")
    assert m.first_time_today("2026-10-16", "festival.today")
    assert not m.first_time_today("2026-10-16", "festival.today")
    assert m.first_time_today("2026-10-17", "festival.today")


def test_farewell_prompt():
    card = load_persona(REPO / "spec" / "examples" / "persona.example.yaml")
    assert "道別模式" in build_system_prompt(card, farewell=True)
    assert "道別模式" not in build_system_prompt(card)
    assert "休息" in build_system_prompt(card, remind_rest=True)


def test_proactive_event_reaches_connected_family():
    with TestClient(main.app) as client:
        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "hello"
            main.engine.cfg.wellbeing.quiet_hours = [3, 3]          # 測試時不受安靜時段影響
            client.portal.call(main.handle_event, main.engine, "weather.rain_soon")
            got = []
            while True:
                m = ws.receive_json()
                if m["type"] == "text_end":
                    break
                got.append(m.get("delta", ""))
            assert "雨傘" in "".join(got)                        # echo LLM 把提示念回來
