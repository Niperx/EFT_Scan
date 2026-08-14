"""Портрет игрока: imagemagic.tarkov.dev или карточка через Pillow."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

from eft_scan.modes import MODE_META
from eft_scan.stats import PlayerCard

IMAGEMAGIC_PLAYER = "https://imagemagic.tarkov.dev/player"

# Компактнее в чате: больше места под текст карточки.
PORTRAIT_MAX_SIDE = 420
FALLBACK_SIZE = (640, 360)

DEFAULT_USEC = {
    "head": "5cc084dd14c02e000b0550a3",
    "body": "5cc0858d14c02e000c6bea66",
    "feet": "5cc085bb14c02e000e67a5c5",
    "hands": "5cc0876314c02e000c6bea6b",
}

_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
)

_BG = (18, 18, 22)
_PANEL = (28, 28, 34)
_TEXT = (236, 232, 223)
_MUTED = (160, 154, 142)
_ACCENT_BEAR = (196, 86, 54)
_ACCENT_USEC = (78, 140, 196)
_ACCENT_ARENA = (201, 162, 39)


def _customization_for_image(payload: dict[str, Any]) -> dict[str, Any]:
    cust = payload.get("customization")
    preset = payload.get("presetCustomization") or {}
    if isinstance(cust, dict) and cust.get("head"):
        return {
            "head": cust.get("head"),
            "body": cust.get("body"),
            "feet": cust.get("feet"),
            "hands": cust.get("hands"),
        }
    if (isinstance(cust, dict) and cust.get("upperSuitId")) or preset.get("upperSuitId"):
        return dict(DEFAULT_USEC)
    if isinstance(cust, dict) and cust:
        return cust
    return dict(DEFAULT_USEC)


def portrait_request_body(payload: dict[str, Any]) -> dict[str, Any]:
    aid = payload.get("aid")
    body: dict[str, Any] = {
        "aid": aid,
        "customization": _customization_for_image(payload),
    }
    equipment = payload.get("equipment")
    if equipment:
        body["equipment"] = equipment
    return body


def portrait_url(payload: dict[str, Any]) -> str:
    body = portrait_request_body(payload)
    aid = body.get("aid") or 0
    encoded = quote(json.dumps(body, separators=(",", ":"), ensure_ascii=False), safe="")
    return f"{IMAGEMAGIC_PLAYER}/{aid}.webp?data={encoded}"


def _font_path() -> Path | None:
    for path in _FONT_CANDIDATES:
        if path.exists():
            return path
    return None


def _load_font(size: int):
    from PIL import ImageFont

    path = _font_path()
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size=size)


def _accent(card: PlayerCard) -> tuple[int, int, int]:
    if card.game_mode == "arena":
        return _ACCENT_ARENA
    if card.side.lower() == "bear":
        return _ACCENT_BEAR
    return _ACCENT_USEC


def _fit_image(image, max_side: int = PORTRAIT_MAX_SIDE):
    from PIL import Image

    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, resample=Image.Resampling.LANCZOS)


def image_to_jpeg(raw: bytes, *, quality: int = 82, max_side: int = PORTRAIT_MAX_SIDE) -> bytes:
    from PIL import Image

    image = Image.open(BytesIO(raw)).convert("RGB")
    image = _fit_image(image, max_side=max_side)
    out = BytesIO()
    image.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue()


def webp_to_jpeg(raw: bytes, *, quality: int = 82, max_side: int = PORTRAIT_MAX_SIDE) -> bytes:
    return image_to_jpeg(raw, quality=quality, max_side=max_side)


def render_fallback_card(card: PlayerCard) -> bytes:
    from PIL import Image, ImageDraw

    width, height = FALLBACK_SIZE
    image = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(image)
    accent = _accent(card)
    draw.rectangle((0, 0, 12, height), fill=accent)
    draw.rounded_rectangle((32, 28, width - 28, height - 28), radius=14, fill=_PANEL)

    title_font = _load_font(30)
    body_font = _load_font(20)
    small_font = _load_font(17)

    meta = MODE_META.get(card.game_mode, {})
    mode_title = f"{meta.get('icon', '')} {meta.get('title', card.game_mode)}"
    y = 48
    draw.text((54, y), card.nickname, font=title_font, fill=_TEXT)
    y += 42
    subtitle = f"ур. {card.level} · {card.side}"
    if card.prestige:
        subtitle += f" · престиж {card.prestige}"
    draw.text((54, y), subtitle, font=body_font, fill=accent)
    y += 32
    draw.text((54, y), mode_title, font=small_font, fill=_MUTED)
    y += 40

    if card.arena is not None:
        lines = [
            f"Матчи {card.arena.games} · победы {card.arena.wins}",
            f"K/D {card.arena.kd_label} · ARP {card.arena.best_arp}",
            f"Стрик {card.arena.longest_win_streak} · {card.hours_played} ч",
        ]
    else:
        lines = [
            f"PMC K/D {card.pmc.pmc_kd_label} · рейды {card.pmc.raids} · выжил {card.pmc.survived}",
            f"Scav K/D {card.scav.kd_label} · рейды {card.scav.raids}",
            f"В игре {card.hours_played} ч · ID {card.account_id}",
        ]
    for line in lines:
        draw.text((54, y), line, font=body_font, fill=_TEXT)
        y += 30

    if card.editions:
        draw.text((54, height - 58), " · ".join(card.editions), font=small_font, fill=_MUTED)

    out = BytesIO()
    image.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()
