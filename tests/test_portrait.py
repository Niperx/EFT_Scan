from __future__ import annotations

import json
from pathlib import Path

from eft_scan.handlers import _card_keyboard, keyboard_modes
from eft_scan.portrait import portrait_request_body, portrait_url, render_fallback_card, webp_to_jpeg
from eft_scan.stats import build_player_card, load_player_levels

PROFILE = Path(__file__).parent / "fixtures" / "profile.json"
ARENA = Path(__file__).parent / "fixtures" / "arena.json"


def _card(path: Path, game_mode: str, available: tuple[str, ...]):
    profile = json.loads(path.read_text(encoding="utf-8"))
    return build_player_card(
        profile,
        game_mode=game_mode,
        levels=load_player_levels(),
        available_modes=available,
    )


def test_keyboard_keeps_other_modes_when_one_is_missing() -> None:
    card = _card(PROFILE, "regular", ("regular", "pve", "arena"))
    modes = keyboard_modes(card)
    assert "pvp-season" not in modes
    assert modes == ("regular", "pve", "arena")
    markup = _card_keyboard(card)
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "· PVP ·" in labels
    assert "Сезон" not in labels
    assert "PVE" in labels
    assert "Арена" in labels
    assert "tarkov.dev" in labels


def test_keyboard_always_includes_current_mode() -> None:
    card = _card(PROFILE, "pvp-season", ("regular",))
    assert keyboard_modes(card) == ("pvp-season", "regular")


def test_portrait_url_uses_head_and_default_suit() -> None:
    payload = {
        "aid": 6976458,
        "customization": {"upperSuitId": "abc"},
        "presetCustomization": {"upperSuitId": "abc"},
    }
    body = portrait_request_body(payload)
    assert body["customization"]["head"] == "5cc084dd14c02e000b0550a3"
    url = portrait_url(payload)
    assert url.startswith("https://imagemagic.tarkov.dev/player/6976458.webp?data=")


def test_portrait_prefers_profile_head() -> None:
    arena = json.loads(ARENA.read_text(encoding="utf-8"))
    from eft_scan.stats import extract_portrait_data

    payload = extract_portrait_data(arena)
    assert payload is not None
    body = portrait_request_body(payload)
    assert body["customization"]["head"] == "60a6aaad42fd2735e4589978"


def test_render_fallback_card_jpeg() -> None:
    card = _card(PROFILE, "regular", ("regular",))
    jpeg = render_fallback_card(card)
    assert jpeg[:2] == b"\xff\xd8"
    from PIL import Image
    from io import BytesIO

    image = Image.open(BytesIO(jpeg))
    assert image.size == (960, 540)


def test_webp_to_jpeg_roundtrip() -> None:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="WEBP")
    jpeg = webp_to_jpeg(buffer.getvalue())
    assert jpeg[:2] == b"\xff\xd8"
