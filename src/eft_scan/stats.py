from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    return round(seconds / 3600)


def build_player_card(
    profile: dict[str, Any],
    *,
    game_mode: str,
    levels: list[dict[str, Any]],
) -> PlayerCard:
    info = profile.get("info") or {}
    experience = int(info.get("experience") or 0)
    level, badge = player_level(experience, levels)
    account_id = str(profile.get("aid") or "")
    mode_path = "regular" if game_mode == "regular" else game_mode
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
        profile_url=f"https://tarkov.dev/players/{mode_path}/{account_id}",
        level_badge=badge,
    )


@dataclass
class PlayerMatch:
    account_id: str
    nickname: str
    exact: bool = False


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
