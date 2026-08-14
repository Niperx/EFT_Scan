from __future__ import annotations

from datetime import datetime
from html import escape

from eft_scan.modes import ARENA, MODE_META, PVP
from eft_scan.stats import ArenaStats, PlayerCard, PlayerMatch, RaidStats

CAPTION_LIMIT = 1024


def mode_label(game_mode: str) -> str:
    meta = MODE_META.get(game_mode)
    if meta:
        return str(meta["short"])
    return game_mode.upper()


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "н/д"
    return value.strftime("%d.%m.%Y %H:%M UTC")


def _plural(n: int, one: str, few: str, many: str) -> str:
    value = abs(n) % 100
    if 11 <= value <= 14:
        word = many
    else:
        last = value % 10
        if last == 1:
            word = one
        elif 2 <= last <= 4:
            word = few
        else:
            word = many
    return f"{n} {word}"


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def survival_bar(rate: float, width: int = 10) -> str:
    filled = max(0, min(width, round(rate * width)))
    return "▰" * filled + "▱" * (width - filled)


def _raid_block(title: str, stats: RaidStats, *, pmc_kd: bool = False) -> str:
    bar = survival_bar(stats.survival_rate)
    if pmc_kd:
        kd_line = (
            f"PMC K/D <code>{escape(stats.pmc_kd_label)}</code>"
            f"  ({stats.pmc_kills}/{stats.deaths})\n"
            f"Убийств <code>{stats.kills}</code> · стрик <code>{stats.longest_streak}</code>"
        )
    else:
        kd_line = (
            f"K/D <code>{escape(stats.kd_label)}</code>"
            f"  ({stats.kills}/{stats.deaths})\n"
            f"PMC <code>{stats.pmc_kills}</code> · стрик <code>{stats.longest_streak}</code>"
        )
    return (
        f"<b>{escape(title)}</b>\n"
        f"{bar}  {_pct(stats.survival_rate)}\n"
        f"Рейды <code>{stats.raids}</code> · выжил <code>{stats.survived}</code>\n"
        f"{kd_line}"
    )


def _arena_block(stats: ArenaStats) -> str:
    lines = [
        "<b>Общий зачёт</b>",
        f"Матчи <code>{stats.games}</code> · победы <code>{stats.wins}</code>  ({_pct(stats.win_rate)})",
        f"K/D <code>{escape(stats.kd_label)}</code>  ({stats.kills}/{stats.deaths})",
        f"ARP <code>{stats.best_arp}</code> · стрик <code>{stats.longest_win_streak}</code>"
        f" · без смертей <code>{stats.max_kills_without_deaths}</code>",
    ]
    if stats.modes:
        lines.append("")
        for mode in stats.modes:
            lines.append(
                f"• {escape(mode.name)} · <code>{mode.games}</code>"
                f" · {_pct(mode.win_rate)}"
                f" · K/D <code>{escape(mode.kd_label)}</code>"
            )
    return "\n".join(lines)


def _mode_header(card: PlayerCard) -> str:
    meta = MODE_META.get(card.game_mode, {})
    icon = str(meta.get("icon") or "🎮")
    title = str(meta.get("title") or card.game_mode)
    hint = str(meta.get("hint") or "")
    inner = [f"{icon} <b>{escape(title)}</b>"]
    if card.is_fallback and card.game_mode == PVP:
        inner.append("<i>Сезонного профиля нет — показан постоянный PVP</i>")
    elif hint:
        inner.append(f"<i>{escape(hint)}</i>")
    return "<blockquote>" + "\n".join(inner) + "</blockquote>"


def format_player_card(card: PlayerCard) -> str:
    side_icon = "🐻" if card.side.lower() == "bear" else "🦅"
    prestige = f" · престиж {card.prestige}" if card.prestige else ""
    editions = escape(" · ".join(card.editions)) if card.editions else ""
    title = (
        f"{side_icon} <b>{escape(card.nickname)}</b>\n"
        f"<code>ур. {card.level}</code> · {escape(card.side)}{prestige}"
    )
    if editions:
        title += f"\n{editions}"
    activity = card.last_active or card.updated
    meta_lines = [
        f"ID <code>{escape(card.account_id)}</code>",
        f"⏱ {card.hours_played} ч · активность {_fmt_dt(activity)}",
    ]
    if card.achievements:
        meta_lines.append(f"🏆 {_plural(card.achievements, 'достижение', 'достижения', 'достижений')}")
    meta_lines.append(
        f'<a href="{escape(card.profile_url, quote=True)}">Открыть на tarkov.dev</a>'
    )
    blocks = [_mode_header(card), title, "\n".join(meta_lines)]
    if card.game_mode == ARENA and card.arena is not None:
        blocks.append(_arena_block(card.arena))
    else:
        blocks.append(_raid_block("PMC", card.pmc, pmc_kd=True))
        blocks.append(_raid_block("Scav", card.scav))
    return "\n\n".join(blocks)


def format_matches(query: str, matches: list[PlayerMatch], game_mode: str) -> str:
    mode = mode_label(game_mode)
    lines = [f"Нашёл несколько игроков по запросу <b>{escape(query)}</b> ({escape(mode)}):"]
    for index, match in enumerate(matches, start=1):
        mark = "✓" if match.exact else "·"
        lines.append(f"{index}. {mark} {escape(match.nickname)} · ID <code>{escape(match.account_id)}</code>")
    lines.append("Выберите игрока кнопкой ниже.")
    return "\n".join(lines)


def format_not_found(query: str, game_mode: str) -> str:
    mode = mode_label(game_mode)
    return (
        f"Игрок <b>{escape(query)}</b> ({escape(mode)}) не найден в индексе tarkov.dev.\n\n"
        "Живой поиск на сайте закрыт Turnstile, поэтому бот смотрит только профили, "
        "которые уже открывали на "
        '<a href="https://tarkov.dev/players">tarkov.dev/players</a>.\n'
        "Откройте профиль там и повторите запрос — индекс обновляется примерно раз в сутки."
    )


def format_help(bot_username: str) -> str:
    mention = f"@{bot_username}" if bot_username else "@bot"
    header = (
        "<blockquote>"
        "🎯 <b>EFT Scan</b>\n"
        "<i>Статистика игрока Escape from Tarkov</i>"
        "</blockquote>"
    )
    intro = (
        "По нику — карточка с <b>PMC K/D</b>, выживаемостью и портретом.\n"
        "По умолчанию <b>сезонный персонаж</b>, если его нет — постоянный PVP."
    )
    group = (
        "<b>В группе</b>\n"
        f"<code>{escape(mention)} Nikita</code>\n"
        f"<code>{escape(mention)} pvp Nikita</code>\n"
        f"<code>{escape(mention)} pve Nikita</code>\n"
        f"<code>{escape(mention)} arena Nikita</code>"
    )
    commands = (
        "<b>Команды</b>\n"
        "/player <code>Nikita</code> — сезон, иначе PVP\n"
        "/season <code>Nikita</code> — только сезон\n"
        "/pvp <code>Nikita</code> — постоянный PVP\n"
        "/pve <code>Nikita</code> — PVE\n"
        "/arena <code>Nikita</code> — Tarkov Arena"
    )
    tips = (
        "В личке можно просто написать ник.\n"
        "Кнопки под карточкой — только режимы, которые есть у аккаунта.\n"
        'Данные: <a href="https://tarkov.dev/api/">tarkov.dev</a>.'
    )
    return "\n\n".join([header, intro, group, commands, tips])


def format_need_nick(bot_username: str) -> str:
    mention = f"@{bot_username}" if bot_username else "@bot"
    return f"Укажите ник после упоминания, например: {escape(mention)} Nikita"


def format_mode_missing(game_mode: str) -> str:
    return f"В режиме {mode_label(game_mode)} профиля нет."
