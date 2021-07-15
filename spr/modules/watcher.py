import os
from pyrogram import filters
from pyrogram.types import Message

from spr import arq, spr, SUDOERS
from spr.utils.db import (add_chat, add_user, chat_exists,
                          is_chat_blacklisted, is_nsfw_enabled,
                          is_spam_enabled, is_user_blacklisted,
                          user_exists, update_spam_data,
                          is_nsfw_downvoted)
from spr.utils.functions import (delete_get_info, delete_nsfw_notify,
                                 delete_spam_notify, kick_user_notify)
from spr.utils.misc import get_file_id


@spr.on_message(
    (
        filters.document
        | filters.photo
        | filters.sticker
        | filters.animation
        | filters.video
        | filters.text
    )
)
async def message_watcher(_, message: Message):
    user_id = None
    chat_id = None

    if message.chat.type in ["group", "supergroup"]:
        chat_id = message.chat.id
        if not chat_exists(chat_id):
            add_chat(chat_id)
        if is_chat_blacklisted(chat_id):
            await spr.leave_chat(chat_id)

    if message.from_user:
        if message.from_user.id:
            user_id = message.from_user.id
            if not user_exists(user_id):
                add_user(user_id)
            if is_user_blacklisted(user_id) and chat_id:
                await kick_user_notify(message)

    if not chat_id or not user_id:
        return

    file_id = get_file_id(message)
    if file_id:
        if user_id in SUDOERS:
            return
        if is_nsfw_downvoted(file_id):
            return
        file = await spr.download_media(file_id)
        resp = await arq.nsfw_scan(file=file)
        os.remove(file)
        if resp.ok:
            if resp.result.is_nsfw:
                if is_nsfw_enabled(chat_id):
                    return await delete_nsfw_notify(
                        message, resp.result
                    )

    text = message.text or message.caption
    if not text:
        return
    resp = await arq.nlp(text)
    if not resp.ok:
        return
    result = resp.result[0]
    update_spam_data(user_id, result.spam)
    if not result.is_spam:
        return
    if not is_spam_enabled(chat_id) or user_id in SUDOERS:
        return
    await delete_spam_notify(
        message, result.spam_probability
    )
