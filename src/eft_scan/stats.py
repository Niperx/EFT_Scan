"""Нормализация профиля игрока Tarkov."""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eft_scan.modes import ARENA, PLAYERS_SITE, SITE_PATH

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_LEVELS_PATH = PACKAGE_DIR / "data" / "player_levels.json"

MEMBER_FLAGS: tuple[tuple[str, int], ...] = (
    ("Developer", 1),
    ("EOD", 2),
    ("ChatModerator", 32),
    ("Sherpa", 256),
    ("Emissary", 512),
    ("Unheard", 1024),
)

ARENA_MODE_LABELS: dict[str, str] = {
    "UnrankedOverall": "Общий зачёт",
    "UnrankedLastHero": "Last Hero",
    "UnrankedCheckPoint": "CheckPoint",
    "UnrankedTeamFight": "TeamFight",
    "UnrankedBlastGang": "BlastGang",
    "UnrankedShootOutDuo": "ShootOut Duo",
}

ARENA_MODE_ORDER = (
    "UnrankedLastHero",
    "UnrankedCheckPoint",
    "UnrankedTeamFight",
    "UnrankedBlastGang",
    "UnrankedShootOutDuo",
)


@dataclass(frozen=True, slots=True)
class RaidStats:
    raids: int
    survived: int
    killed: int
    runner: int
    kills: int
    deaths: int
    pmc_kills: int
    longest_streak: int

    @property
    def survival_rate(self) -> float:
        if self.raids <= 0:
            return 0.0
        return self.survived / self.raids

    @property
    def kd_label(self) -> str:
        if self.deaths <= 0:
            return "∞" if self.kills > 0 else "0.00"
        return f"{self.kills / self.deaths:.2f}"

    @property
    def pmc_kd_label(self) -> str:
        """K/D по убийствам PMC (без AI/Scav)."""
        if self.deaths <= 0:
            return "∞" if self.pmc_kills > 0 else "0.00"
        return f"{self.pmc_kills / self.deaths:.2f}"


@dataclass(frozen=True, slots=True)
class ArenaModeLine:
    key: str
    name: str
    games: int
    wins: int
    kills: int
    deaths: int
    kd_label: str
    win_rate: float


@dataclass(frozen=True, slots=True)
class ArenaStats:
    games: int
    wins: int
    kills: int
    deaths: int
    kd_label: str
    win_rate: float
    best_arp: int
    longest_win_streak: int
    max_kills_without_deaths: int
    modes: tuple[ArenaModeLine, ...]


@dataclass(frozen=True, slots=True)
class PlayerCard:
    account_id: str
    nickname: str
    side: str
    level: int
    prestige: int
    experience: int
    editions: tuple[str, ...]
    hours_played: int
    last_active: datetime | None
    updated: datetime | None
    pmc: RaidStats
    scav: RaidStats
    achievements: int
    game_mode: str
    profile_url: str
    level_badge: str | None = None
    is_fallback: bool = False
    arena: ArenaStats | None = None
    available_modes: tuple[str, ...] = ()
    portrait_data: dict[str, Any] | None = None


def load_player_levels(path: Path | None = None) -> list[dict[str, Any]]:
    with (path or DEFAULT_LEVELS_PATH).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict) and "data" in payload:
        return list(payload["data"])
    return list(payload)


def player_level(experience: int, levels: list[dict[str, Any]]) -> tuple[int, str | None]:
    if experience <= 0 or not levels:
        return 1, None
    total = 0
    for index, row in enumerate(levels):
        total += int(row.get("exp") or 0)
        if total == experience:
            return int(row["level"]), row.get("levelBadgeImageLink")
        if total > experience:
            previous = levels[index - 1] if index > 0 else row
            return int(previous["level"]), previous.get("levelBadgeImageLink")
    last = levels[-1]
    return int(last["level"]), last.get("levelBadgeImageLink")


def member_editions(member_category: int) -> tuple[str, ...]:
    return tuple(name for name, flag in MEMBER_FLAGS if member_category & flag)


def _counter_value(items: list[dict[str, Any]], *needles: str) -> int:
    for item in items:
        key = item.get("Key") or []
        if all(part in key for part in needles):
            return int(item.get("Value") or 0)
    return 0


def parse_raid_stats(blob: dict[str, Any] | None) -> RaidStats:
    items = ((blob or {}).get("eft") or {}).get("overAllCounters", {}).get("Items") or []
    return RaidStats(
        raids=_counter_value(items, "Sessions"),
        survived=_counter_value(items, "Survived"),
        killed=_counter_value(items, "Killed"),
        runner=_counter_value(items, "Runner"),
        kills=_counter_value(items, "Kills"),
        deaths=_counter_value(items, "Deaths"),
        pmc_kills=_counter_value(items, "KilledPmc"),
        longest_streak=_counter_value(items, "LongestWinStreak"),
    )


def _arena_counters(blob: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(blob, dict):
        return {}
    inner = blob.get("Counters")
    if isinstance(inner, dict):
        return inner
    return blob


def _kd_label(kills: int, deaths: int) -> str:
    if deaths <= 0:
        return "∞" if kills > 0 else "0.00"
    return f"{kills / deaths:.2f}"


def _arena_mode_line(key: str, raw: dict[str, Any] | None) -> ArenaModeLine:
    counters = _arena_counters(raw)

    def n(name: str) -> int:
        return int(counters.get(name) or 0)

    games = n("GamesCount")
    wins = n("ArenaWins") or n("Wins")
    kills = n("Kills")
    deaths = n("Deaths")
    return ArenaModeLine(
        key=key,
        name=ARENA_MODE_LABELS.get(key, key),
        games=games,
        wins=wins,
        kills=kills,
        deaths=deaths,
        kd_label=_kd_label(kills, deaths),
        win_rate=(wins / games) if games else 0.0,
    )


def parse_arena_stats(profile: dict[str, Any]) -> ArenaStats | None:
    counters = ((profile.get("stat") or {}).get("arenaOverAllCounters")) or {}
    if not isinstance(counters, dict) or not counters:
        return None
    overall = _arena_mode_line("UnrankedOverall", counters.get("UnrankedOverall"))
    modes = tuple(
        line
        for key in ARENA_MODE_ORDER
        if (line := _arena_mode_line(key, counters.get(key))).games > 0
    )
    wins = overall.wins or sum(line.wins for line in modes)
    games = overall.games
    overall_raw = _arena_counters(counters.get("UnrankedOverall"))
    return ArenaStats(
        games=games,
        wins=wins,
        kills=overall.kills,
        deaths=overall.deaths,
        kd_label=_kd_label(overall.kills, overall.deaths),
        win_rate=(wins / games) if games else 0.0,
        best_arp=int(overall_raw.get("BestArp") or 0),
        longest_win_streak=int(overall_raw.get("LongestWinStreak") or 0),
        max_kills_without_deaths=int(overall_raw.get("MaxKillsWithoutDeaths") or 0),
        modes=modes,
    )


def _last_active(profile: dict[str, Any]) -> datetime | None:
    skills = ((profile.get("skills") or {}).get("Common")) or []
    latest = 0
    for skill in skills:
        stamp = int(skill.get("LastAccess") or 0)
        if stamp > latest:
            latest = stamp
    if latest <= 0:
        return None
    return datetime.fromtimestamp(latest, tz=timezone.utc)


def _updated_at(profile: dict[str, Any]) -> datetime | None:
    raw = profile.get("updated")
    if not raw:
        return None
    millis = int(raw)
    if millis > 10_000_000_000:
        millis //= 1000
    return datetime.fromtimestamp(millis, tz=timezone.utc)


def hours_played(profile: dict[str, Any]) -> int:
    seconds = int(((profile.get("pmcStats") or {}).get("eft") or {}).get("totalInGameTime") or 0)
    if not seconds:
        seconds = int((profile.get("stat") or {}).get("totalInGameTime") or 0)
    return round(seconds / 3600)


def extract_portrait_data(profile: dict[str, Any]) -> dict[str, Any] | None:
    aid = profile.get("aid")
    customization = profile.get("customization") or profile.get("profileCustomization")
    preset = profile.get("presetCustomization") or {}
    equipment = profile.get("equipment")
    if not customization and not preset and not equipment:
        return None
    payload: dict[str, Any] = {"aid": aid}
    if isinstance(customization, dict):
        payload["customization"] = customization
    if isinstance(preset, dict) and preset:
        payload["presetCustomization"] = preset
    if equipment:
        payload["equipment"] = equipment
    return payload


def build_player_card(
    profile: dict[str, Any],
    *,
    game_mode: str,
    levels: list[dict[str, Any]],
    is_fallback: bool = False,
    available_modes: tuple[str, ...] = (),
) -> PlayerCard:
    info = profile.get("info") or {}
    experience = int(info.get("experience") or 0)
    level, badge = player_level(experience, levels)
    account_id = str(profile.get("aid") or info.get("aid") or "")
    mode_path = SITE_PATH.get(game_mode, game_mode)
    arena = parse_arena_stats(profile) if game_mode == ARENA else None
    return PlayerCard(
        account_id=account_id,
        nickname=str(info.get("nickname") or "Unknown"),
        side=str(info.get("side") or "—"),
        level=level,
        prestige=int(info.get("prestigeLevel") or 0),
        experience=experience,
        editions=member_editions(int(info.get("memberCategory") or 0)),
        hours_played=hours_played(profile),
        last_active=_last_active(profile),
        updated=_updated_at(profile),
        pmc=parse_raid_stats(profile.get("pmcStats")),
        scav=parse_raid_stats(profile.get("scavStats")),
        achievements=len(profile.get("achievements") or {}),
        game_mode=game_mode,
        profile_url=f"{PLAYERS_SITE}/{mode_path}/{account_id}",
        level_badge=badge,
        is_fallback=is_fallback,
        arena=arena,
        available_modes=available_modes,
        portrait_data=extract_portrait_data(profile),
    )


@dataclass
class PlayerMatch:
    account_id: str
    nickname: str
    exact: bool = False


def pick_single_match(matches: list[PlayerMatch]) -> PlayerMatch | None:
    if len(matches) == 1:
        return matches[0]
    exact = [item for item in matches if item.exact]
    if len(exact) == 1:
        return exact[0]
    return None


def search_index(
    aid_to_name: dict[str, str],
    sorted_names: list[str],
    name_to_aids: dict[str, list[str]],
    query: str,
    *,
    limit: int = 8,
) -> list[PlayerMatch]:
    raw = query.strip()
    if not raw:
        return []
    if raw.isdigit() and raw in aid_to_name:
        return [PlayerMatch(raw, aid_to_name[raw], exact=True)]

    key = raw.lower()
    exact_aids = name_to_aids.get(key, [])
    if exact_aids:
        return [PlayerMatch(aid, aid_to_name[aid], exact=True) for aid in exact_aids[:limit]]

    matches: list[PlayerMatch] = []
    index = bisect.bisect_left(sorted_names, key)
    while index < len(sorted_names) and sorted_names[index].startswith(key):
        for aid in name_to_aids.get(sorted_names[index], []):
            matches.append(PlayerMatch(aid, aid_to_name[aid], exact=False))
            if len(matches) >= limit:
                return matches
        index += 1

    if matches or len(key) < 4:
        return matches

    for name, aids in name_to_aids.items():
        if key in name:
            for aid in aids:
                matches.append(PlayerMatch(aid, aid_to_name[aid], exact=False))
                if len(matches) >= limit:
                    return matches
    return matches
