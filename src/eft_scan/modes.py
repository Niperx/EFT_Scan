from __future__ import annotations

AUTO = "auto"
PVP_SEASON = "pvp-season"
PVP = "regular"
PVE = "pve"

PROFILE_PATH = {
    PVP: "profile",
    PVE: "pve",
    PVP_SEASON: "pvp-season",
}

MODE_META = {
    PVP_SEASON: {
        "icon": "🎯",
        "short": "Сезон",
        "title": "Сезонный персонаж",
        "hint": "PVP Season · текущий вайп",
    },
    PVP: {
        "icon": "⚔️",
        "short": "PVP",
        "title": "Постоянный PVP",
        "hint": "Классический персонаж, не сезон",
    },
    PVE: {
        "icon": "🛡️",
        "short": "PVE",
        "title": "PVE-персонаж",
        "hint": "Кооператив против ИИ",
    },
}


def lookup_order(game_mode: str) -> tuple[str, ...]:
    if game_mode in (AUTO, "player", ""):
        return (PVP_SEASON, PVP)
    return (game_mode,)
