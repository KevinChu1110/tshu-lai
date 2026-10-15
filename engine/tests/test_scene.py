from tshulai.scene import SceneMachine, load_scenes


def test_homecoming_then_sit_then_tv():
    m = SceneMachine(load_scenes())
    assert m.current.id == "chat"
    assert m.on_event("geofence.enter:home").id == "homecoming"
    assert m.on_event("motion.sit_down").id == "sitting"
    assert m.on_event("tv.program_started").id == "tv"
    assert m.on_event("geofence.exit:home").id == "chat"  # 離開家回到閒聊通道


def test_unknown_event_no_change():
    m = SceneMachine(load_scenes())
    assert m.on_event("nothing") is None
