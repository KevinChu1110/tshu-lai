from pathlib import Path

import pytest

from tshulai.persona import build_system_prompt, load_persona

EXAMPLE = Path(__file__).resolve().parents[2] / "spec" / "examples" / "persona.example.yaml"


def test_example_card_validates():
    card = load_persona(EXAMPLE)
    assert card.display_name == "阿嬤"
    assert card.primary_language == "nan-TW"


def test_taboo_is_last_and_strong():
    card = load_persona(EXAMPLE)
    prompt = build_system_prompt(card, user_name="冠融")
    assert "她的病情" in prompt
    assert prompt.index("絕對不講") > prompt.index("你的口頭禪")
    assert "冠融" in prompt


def test_invalid_card_rejected(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\ndisplay_name: 阿嬤\n", encoding="utf-8")  # 缺 languages 與 consent
    with pytest.raises(ValueError):
        load_persona(bad)
