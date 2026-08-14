from __future__ import annotations

import logging
from io import BytesIO

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, InputMediaPhoto, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from eft_scan.client import ProfileMissingError, TarkovClient, TarkovError
from eft_scan.format import (
    CAPTION_LIMIT,
    format_help,
    format_matches,
    format_need_nick,
    format_not_found,
    format_player_card,
)
from eft_scan.modes import MODE_META, MODE_ORDER
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


def keyboard_modes(card: PlayerCard) -> tuple[str, ...]:
    present = set(card.available_modes or MODE_ORDER)
    present.add(card.game_mode)
    return tuple(mode for mode in MODE_ORDER if mode in present)


def _card_keyboard(card: PlayerCard) -> InlineKeyboardMarkup:
    buttons = []
    for mode in keyboard_modes(card):
        meta = MODE_META[mode]
        label = str(meta["short"])
        if mode == card.game_mode:
            label = f"· {label} ·"
        buttons.append(
            InlineKeyboardButton(label, callback_data=f"p:{mode}:{card.account_id}"),
        )
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("tarkov.dev", url=card.profile_url)])
    return InlineKeyboardMarkup(rows)


def _photo_file(image: bytes, account_id: str) -> InputFile:
    buffer = BytesIO(image)
    buffer.name = f"{account_id}.jpg"
    return InputFile(buffer, filename=buffer.name)


def _message_entities(update: Update) -> list[TextEntity]:
    message = update.effective_message
    if not message:
        return []
    return [
        TextEntity(type=entity.type, offset=entity.offset, length=entity.length)
        for entity in (message.entities or [])
    ]


async def _reply_card(
    update: Update,
    card: PlayerCard,
    *,
    status_message=None,
    client: TarkovClient | None = None,
) -> None:
    text = format_player_card(card)
    markup = _card_keyboard(card)
    photo: bytes | None = None
    if client is not None:
        photo = await client.card_image(card)
    caption = text if len(text) <= CAPTION_LIMIT else None

    if update.callback_query:
        query = update.callback_query
        message = query.message
        if photo is not None:
            media = InputMediaPhoto(
                media=_photo_file(photo, card.account_id),
                caption=caption or card.nickname,
                parse_mode=ParseMode.HTML,
            )
            try:
                await query.edit_message_media(media=media, reply_markup=markup)
                if caption is None and message:
                    await message.reply_html(text, disable_web_page_preview=True)
                return
            except BadRequest:
                logger.info("Не вышло заменить медиа, отправляю новое сообщение")
                if message:
                    try:
                        await message.delete()
                    except BadRequest:
                        pass
                    await message.chat.send_photo(
                        photo=_photo_file(photo, card.account_id),
                        caption=caption or card.nickname,
                        parse_mode=ParseMode.HTML,
                        reply_markup=markup,
                    )
                    if caption is None:
                        await message.chat.send_message(
                            text,
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True,
                        )
                    return
        try:
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=markup,
            )
        except BadRequest:
            await query.edit_message_caption(
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        return

    chat_message = update.effective_message
    if photo is not None and chat_message:
        if status_message is not None:
            try:
                await status_message.delete()
            except BadRequest:
                pass
        await chat_message.reply_photo(
            photo=_photo_file(photo, card.account_id),
            caption=caption or card.nickname,
            parse_mode=ParseMode.HTML,
            reply_markup=markup,
        )
        if caption is None:
            await chat_message.reply_html(text, disable_web_page_preview=True)
        return

    if status_message is not None:
        await status_message.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=markup,
        )
        return
    if chat_message:
        await chat_message.reply_html(text, disable_web_page_preview=True, reply_markup=markup)


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
            await _reply_card(update, result.card, status_message=status, client=client)
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
    try:
        _, game_mode, account_id = query.data.split(":", 2)
    except ValueError:
        await query.answer()
        await query.edit_message_text("Некорректный выбор.")
        return
    try:
        card = await _client(context).card_for_account(account_id, game_mode)
    except ProfileMissingError as exc:
        await query.answer(str(exc)[:200], show_alert=True)
        return
    except TarkovError as exc:
        await query.answer(str(exc)[:200], show_alert=True)
        return
    except Exception:
        logger.exception("Ошибка загрузки профиля %s", account_id)
        await query.answer("Не получилось получить профиль. Попробуйте позже.", show_alert=True)
        return
    await query.answer()
    await _reply_card(update, card, client=_client(context))
