from __future__ import annotations

AUTO = "auto"
PVP_SEASON = "pvp-season"
PVP = "regular"
PVE = "pve"
ARENA = "arena"

PROFILE_PATH = {
    PVP: "profile",
    PVE: "pve",
    PVP_SEASON: "pvp-season",
    ARENA: "arena",
}

MODE_ORDER = (PVP_SEASON, PVP, PVE, ARENA)

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
        "hint": "Классический персонаж",
    },
    PVE: {
        "icon": "🛡️",
        "short": "PVE",
        "title": "PVE-персонаж",
        "hint": "Кооператив против ИИ",
    },
    ARENA: {
        "icon": "🏟️",
        "short": "Арена",
        "title": "Tarkov Arena",
        "hint": "Отдельный профиль Arena",
    },
}

SITE_PATH = {
    PVP: "regular",
    PVE: "pve",
    PVP_SEASON: "pvp-season",
    ARENA: "arena",
}

PLAYERS_SITE = "https://tarkov.dev/players"


def lookup_order(game_mode: str) -> tuple[str, ...]:
    if game_mode in (AUTO, "player", ""):
        return (PVP_SEASON, PVP)
    return (game_mode,)
