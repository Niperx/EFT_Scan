from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from eft_scan.client import TarkovClient, TarkovError
from eft_scan.format import (
    format_help,
    format_matches,
    format_need_nick,
    format_not_found,
    format_player_card,
)
from eft_scan.modes import MODE_META, PVE, PVP, PVP_SEASON
from eft_scan.parse import ParsedQuery, TextEntity, nickname_error, parse_command, parse_mention, parse_private_text
from eft_scan.stats import PlayerCard, PlayerMatch

logger = logging.getLogger(__name__)

MAX_BUTTONS = 8


def _client(context: ContextTypes.DEFAULT_TYPE) -> TarkovClient:
    return context.application.bot_data["tarkov"]


def _bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    return (context.bot.username or "").lstrip("@")


def _match_keyboard(matches: list[PlayerMatch], game_mode: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{match.nickname} ({match.account_id})",
                callback_data=f"p:{game_mode}:{match.account_id}",
            )
        ]
        for match in matches[:MAX_BUTTONS]
    ]
    return InlineKeyboardMarkup(rows)


def _card_keyboard(card: PlayerCard) -> InlineKeyboardMarkup:
    mode_buttons = []
    for mode in (PVP_SEASON, PVP, PVE):
        meta = MODE_META[mode]
        label = str(meta["short"])
        if mode == card.game_mode:
            label = f"· {label} ·"
        mode_buttons.append(
            InlineKeyboardButton(label, callback_data=f"p:{mode}:{card.account_id}"),
        )
    return InlineKeyboardMarkup(
        [
            mode_buttons,
            [InlineKeyboardButton("tarkov.dev", url=card.profile_url)],
        ]
    )


def _message_entities(update: Update) -> list[TextEntity]:
    message = update.effective_message
    if not message:
        return []
    return [
        TextEntity(type=entity.type, offset=entity.offset, length=entity.length)
        for entity in (message.entities or [])
    ]


async def _reply_card(update: Update, card: PlayerCard, status_message=None) -> None:
    text = format_player_card(card)
    markup = _card_keyboard(card)
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=markup,
        )
        return
    if status_message is not None:
        await status_message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=markup,
        )
        return
    message = update.effective_message
    if message:
        await message.reply_html(text, disable_web_page_preview=True, reply_markup=markup)


async def resolve_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: ParsedQuery) -> None:
    message = update.effective_message
    if not message:
        return
    bot_username = _bot_username(context)
    error = nickname_error(parsed.nickname)
    if error:
        if parsed.source == "mention" and not parsed.nickname:
            await message.reply_html(format_need_nick(bot_username))
        else:
            await message.reply_text(error)
        return

    status = await message.reply_text("Ищу игрока…")
    client = _client(context)
    try:
        result = await client.lookup(parsed.nickname, parsed.game_mode)
        if result.not_found:
            await status.edit_text(
                format_not_found(parsed.nickname, result.game_mode),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return
        if result.card is not None:
            await _reply_card(update, result.card, status)
            return
        await status.edit_text(
            format_matches(parsed.nickname, list(result.matches), result.game_mode),
            parse_mode=ParseMode.HTML,
            reply_markup=_match_keyboard(list(result.matches), result.game_mode),
        )
    except TarkovError as exc:
        await status.edit_text(str(exc))
    except Exception:
        logger.exception("Ошибка поиска игрока %s", parsed.nickname)
        await status.edit_text("Не получилось получить профиль. Попробуйте позже.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_html(format_help(_bot_username(context)))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def player_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return
    parsed = parse_command(message.text or "", _bot_username(context))
    if parsed is None:
        await message.reply_text("Использование: /player Ник")
        return
    await resolve_and_reply(update, context, parsed)


async def mention_or_private(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message or not message.text:
        return
    bot_username = _bot_username(context)
    parsed = parse_mention(message.text, _message_entities(update), bot_username)
    if parsed is None and message.chat and message.chat.type == ChatType.PRIVATE:
        parsed = parse_private_text(message.text)
    if parsed is None:
        return
    await resolve_and_reply(update, context, parsed)


async def pick_player(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    try:
        _, game_mode, account_id = query.data.split(":", 2)
    except ValueError:
        await query.edit_message_text("Некорректный выбор.")
        return
    try:
        card = await _client(context).card_for_account(account_id, game_mode)
    except TarkovError as exc:
        await query.edit_message_text(str(exc))
        return
    except Exception:
        logger.exception("Ошибка загрузки профиля %s", account_id)
        await query.edit_message_text("Не получилось получить профиль. Попробуйте позже.")
        return
    await _reply_card(update, card)
