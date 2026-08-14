"""Меню команд Telegram и тексты для BotFather."""

from __future__ import annotations

from telegram import BotCommand

# Лимиты BotFather: About ≤120, Description ≤512.
BOT_ABOUT = (
    "Статистика игроков Escape from Tarkov: сезон, PVP, PVE и Arena по нику."
)

BOT_DESCRIPTION = (
    "EFT Scan — статистика игрока Escape from Tarkov по нику.\n"
    "\n"
    "Сезон · PVP · PVE · Tarkov Arena\n"
    "Карточка с PMC K/D, выживаемостью и портретом персонажа.\n"
    "\n"
    "В личке напишите ник. В группе: @бот Ник\n"
    "Команды: /player /season /pvp /pve /arena\n"
    "\n"
    "Данные: tarkov.dev"
)

BOT_COMMANDS: tuple[BotCommand, ...] = (
    BotCommand("start", "О боте и как пользоваться"),
    BotCommand("help", "Справка по командам"),
    BotCommand("player", "Статистика: сезон, иначе PVP"),
    BotCommand("season", "Сезонный персонаж"),
    BotCommand("pvp", "Постоянный PVP"),
    BotCommand("pve", "PVE-персонаж"),
    BotCommand("arena", "Tarkov Arena"),
)


def botfather_copy() -> str:
    return (
        "=== About (до 120 символов) ===\n"
        f"{BOT_ABOUT}\n\n"
        "=== Description (до кнопки Start, до 512) ===\n"
        f"{BOT_DESCRIPTION}\n"
    )
