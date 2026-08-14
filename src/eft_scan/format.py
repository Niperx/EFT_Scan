from __future__ import annotations

from datetime import datetime
from html import escape

from eft_scan.modes import MODE_META, PVP
from eft_scan.stats import PlayerCard, PlayerMatch, RaidStats


def mode_label(game_mode: str) -> str:
    meta = MODE_META.get(game_mode)
    if meta:
        return str(meta["short"])
    return game_mode.upper()


def _fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "н/д"
    return value.strftime("%d.%m.%Y %H:%M UTC")


def _raid_block(title: str, stats: RaidStats) -> str:
    survival = f"{stats.survival_rate * 100:.1f}%".replace(".", ",")
    return (
        f"<b>{escape(title)}</b>\n"
        f"Рейды: {stats.raids}\n"
        f"Выживаемость: {survival} ({stats.survived})\n"
        f"K/D: {stats.kd_label} ({stats.kills}/{stats.deaths})\n"
        f"Убито PMC: {stats.pmc_kills}\n"
        f"Стрик: {stats.longest_streak}"
    )


def _mode_header(card: PlayerCard) -> str:
    meta = MODE_META.get(card.game_mode, {})
    icon = str(meta.get("icon") or "🎮")
    title = str(meta.get("title") or card.game_mode)
    hint = str(meta.get("hint") or "")
    lines = [f"{icon} <b>{escape(title)}</b>"]
    if card.is_fallback and card.game_mode == PVP:
        lines.append("<i>Сезонного профиля нет — показан постоянный PVP</i>")
    elif hint:
        lines.append(f"<i>{escape(hint)}</i>")
    return "\n".join(lines)


def format_player_card(card: PlayerCard) -> str:
    side_icon = "🐻" if card.side.lower() == "bear" else "🦅"
    prestige = f" · престиж {card.prestige}" if card.prestige else ""
    editions = f"\n{escape(', '.join(card.editions))}" if card.editions else ""
    title = (
        f"{side_icon} <b>{escape(card.nickname)}</b> · "
        f"ур. {card.level} {escape(card.side)}{prestige}"
    )
    meta = (
        f"ID {escape(card.account_id)}{editions}\n"
        f"В игре: {card.hours_played} ч\n"
        f"Активность: {_fmt_dt(card.last_active)}\n"
        f"Достижения: {card.achievements}\n"
        f'<a href="{escape(card.profile_url, quote=True)}">Открыть на tarkov.dev</a>'
    )
    updated = f"\nОбновлено: {_fmt_dt(card.updated)}"
    return "\n\n".join(
        [
            _mode_header(card),
            title,
            meta + updated,
            _raid_block("PMC", card.pmc),
            _raid_block("Scav", card.scav),
        ]
    )


def format_matches(query: str, matches: list[PlayerMatch], game_mode: str) -> str:
    mode = mode_label(game_mode)
    lines = [f"Нашёл несколько игроков по запросу <b>{escape(query)}</b> ({escape(mode)}):"]
    for index, match in enumerate(matches, start=1):
        mark = "✓" if match.exact else "·"
        lines.append(f"{index}. {mark} {escape(match.nickname)} · ID {escape(match.account_id)}")
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
    return (
        "Я показываю статистику игрока Escape from Tarkov по нику.\n"
        "По умолчанию — <b>сезонный персонаж</b>, если его нет — постоянный PVP.\n\n"
        "<b>В группе</b>\n"
        f"{escape(mention)} Nikita\n"
        f"{escape(mention)} pvp Nikita\n"
        f"{escape(mention)} pve Nikita\n\n"
        "<b>Команды</b>\n"
        "/player Nikita — сезон, иначе PVP\n"
        "/season Nikita — только сезон\n"
        "/pvp Nikita — постоянный PVP\n"
        "/pve Nikita — PVE\n\n"
        "В личке можно просто написать ник.\n"
        "Данные: <a href=\"https://tarkov.dev/api/\">tarkov.dev</a>."
    )


def format_need_nick(bot_username: str) -> str:
    mention = f"@{bot_username}" if bot_username else "@bot"
    return f"Укажите ник после упоминания, например: {escape(mention)} Nikita"
