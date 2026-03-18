import os
import logging
import random
import asyncio
from validators import domain
from Script import script
from plugins.dbusers import db
from pyrogram import Client, filters, enums
from plugins.users_api import get_user, update_user_info
from pyrogram.errors import ChatAdminRequired, FloodWait, UserNotParticipant
from pyrogram.types import *
from utils import verify_user, check_token, check_verification, get_token
from config import *
import re
import json
import base64
from urllib.parse import quote_plus
from TechVJ.utils.file_properties import get_name, get_hash, get_media_file_size
logger = logging.getLogger(__name__)

BATCH_FILES = {}


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])

def formate_file_name(file_name):
    chars = ["[", "]", "(", ")"]
    for c in chars:
        file_name.replace(c, "")
    file_name = ' '.join(filter(lambda x: not x.startswith('http') and not x.startswith('@') and not x.startswith('www.'), file_name.split()))
    return file_name


async def check_force_sub(client, user_id):
    if not await db.is_fsub_enabled():
        return []
    channels = await db.get_fsub_channels()
    not_joined = []
    for ch_id in channels:
        try:
            member = await client.get_chat_member(ch_id, user_id)
            if member.status.name in ("BANNED", "LEFT"):
                not_joined.append(ch_id)
        except UserNotParticipant:
            not_joined.append(ch_id)
        except Exception as e:
            logger.warning(f"Force sub check error for {ch_id}: {e}")
    return not_joined


async def get_fsub_buttons(client, not_joined_channels):
    buttons = []
    for i, ch_id in enumerate(not_joined_channels):
        try:
            chat = await client.get_chat(ch_id)
            if chat.username:
                url = f"https://t.me/{chat.username}"
            else:
                invite = await client.create_chat_invite_link(ch_id)
                url = invite.invite_link
            buttons.append([InlineKeyboardButton(f"Join Channel {i+1}", url=url)])
        except Exception as e:
            logger.error(f"get_fsub_buttons error: {e}")
    buttons.append([InlineKeyboardButton("I Joined All Channels", callback_data="fsub_check")])
    return InlineKeyboardMarkup(buttons)


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    username = client.me.username
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        await client.send_message(LOG_CHANNEL, script.LOG_TEXT.format(message.from_user.id, message.from_user.mention))
    if await db.is_banned(message.from_user.id):
        return await message.reply_text("<b>You are banned. Contact @GTK26.</b>", parse_mode=enums.ParseMode.HTML)
    if len(message.command) != 2:
        buttons = [[
            InlineKeyboardButton('🌸 Jᴏɪɴ ᴏᴜʀ ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ', url='https://t.me/infinite_animes')
            ],[
            InlineKeyboardButton('🔍 ᴀɴɪᴍᴇ sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url='https://t.me/animeinhindifangroup'),
            InlineKeyboardButton('🎌 ɪɴғɪɴɪᴛᴇ ᴅʀᴀᴍᴀs', url='https://t.me/infinite_dramas')
            ],[
            InlineKeyboardButton('🎭 ᴅʀᴀᴍᴀ sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ', url='https://t.me/+dxm_jP224jI3ZjFl'),
            InlineKeyboardButton('👨‍💻 ᴅᴇᴠᴇʟᴏᴘᴇʀ', url='https://t.me/GTK26')
        ]]
        if CLONE_MODE == True:
            buttons.append([InlineKeyboardButton('🤖 ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ᴄʟᴏɴᴇ ʙᴏᴛ', callback_data='clone')])
        reply_markup = InlineKeyboardMarkup(buttons)
        me = client.me
        await message.reply_photo(
            photo=random.choice(PICS),
            caption=script.START_TXT.format(message.from_user.mention, me.mention),
            reply_markup=reply_markup,
            message_effect_id=5104841245755180586
        )
        return

    data = message.command[1]
    try:
        pre, file_id = data.split('_', 1)
    except:
        file_id = data
        pre = ""

    if data.split("-", 1)[0] == "verify":
        userid = data.split("-", 2)[1]
        token = data.split("-", 3)[2]
        if str(message.from_user.id) != str(userid):
            return await message.reply_text(
                text="<b>Invalid link or Expired link !</b>",
                protect_content=True
            )
        is_valid = await check_token(client, userid, token)
        if is_valid == True:
            await message.reply_text(
                text=f"<b>Hey {message.from_user.mention}, You are successfully verified !\nNow you have unlimited access for all files till today midnight.</b>",
                protect_content=True
            )
            await verify_user(client, userid, token)
        else:
            return await message.reply_text(
                text="<b>Invalid link or Expired link !</b>",
                protect_content=True
            )

    elif data.split("-", 1)[0] == "BATCH":
        not_joined = await check_force_sub(client, message.from_user.id)
        if not_joined:
            kb = await get_fsub_buttons(client, not_joined)
            return await message.reply_photo(
                photo=random.choice(PICS),
                caption="<b>Please join all channels first!</b>",
                reply_markup=kb,
                parse_mode=enums.ParseMode.HTML
            )
        try:
            if not await check_verification(client, message.from_user.id) and VERIFY_MODE == True:
                btn = [[
                    InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://telegram.me/{username}?start="))
                ],[
                    InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)
                ]]
                await message.reply_text(
                    text="<b>You are not verified !\nKindly verify to continue !</b>",
                    protect_content=True,
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return
        except Exception as e:
            return await message.reply_text(f"**Error - {e}**")
        sts = await message.reply("**Please Wait...**")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            decode_file_id = base64.urlsafe_b64decode(file_id + "=" * (-len(file_id) % 4)).decode("ascii")
            msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
            media = getattr(msg, msg.media.value)
            file_id = media.file_id
            file = await client.download_media(file_id)
            try:
                with open(file) as file_data:
                    msgs=json.loads(file_data.read())
            except:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs
        filesarr = []
        for msg in msgs:
            channel_id = int(msg.get("channel_id"))
            msgid = msg.get("msg_id")
            info = await client.get_messages(channel_id, int(msgid))
            if info.media:
                file_type = info.media
                file = getattr(info, file_type.value)
                f_caption = getattr(info, 'caption', '')
                if f_caption:
                    f_caption = f_caption.html
                old_title = getattr(file, "file_name", "")
                title = formate_file_name(old_title)
                size=get_size(int(file.file_size))
                if BATCH_FILE_CAPTION:
                    try:
                        f_caption=BATCH_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='' if f_caption is None else f_caption)
                    except:
                        f_caption=f_caption
                if f_caption is None:
                    f_caption = title
                if STREAM_MODE == True:
                    if info.video or info.document:
                        log_msg = info
                        stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                        button = [[
                            InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                            InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                        ],[
                            InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                        ]]
                        reply_markup=InlineKeyboardMarkup(button)
                else:
                    reply_markup = None
                try:
                    msg = await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=False, reply_markup=reply_markup)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(chat_id=message.from_user.id, caption=f_caption, protect_content=False, reply_markup=reply_markup)
                except:
                    continue
            else:
                try:
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    msg = await info.copy(chat_id=message.from_user.id, protect_content=False)
                except:
                    continue
            filesarr.append(msg)
            await asyncio.sleep(1)
        await sts.delete()
        if AUTO_DELETE_MODE == True:
            k = await client.send_message(chat_id=message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{AUTO_DELETE} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(AUTO_DELETE_TIME)
            for x in filesarr:
                try:
                    await x.delete()
                except:
                    pass
            await k.edit_text("<b>Your All Files/Videos is successfully deleted!!!</b>")
        return

    not_joined = await check_force_sub(client, message.from_user.id)
    if not_joined:
        kb = await get_fsub_buttons(client, not_joined)
        return await message.reply_photo(
            photo=random.choice(PICS),
            caption="<b>Please join all channels first!</b>",
            reply_markup=kb,
            parse_mode=enums.ParseMode.HTML
        )

    pre, decode_file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
    if not await check_verification(client, message.from_user.id) and VERIFY_MODE == True:
        btn = [[
            InlineKeyboardButton("Verify", url=await get_token(client, message.from_user.id, f"https://telegram.me/{username}?start="))
        ],[
            InlineKeyboardButton("How To Open Link & Verify", url=VERIFY_TUTORIAL)
        ]]
        await message.reply_text(
            text="<b>You are not verified !\nKindly verify to continue !</b>",
            protect_content=True,
            reply_markup=InlineKeyboardMarkup(btn)
        )
        return
    try:
        msg = await client.get_messages(LOG_CHANNEL, int(decode_file_id))
        if msg.media:
            media = getattr(msg, msg.media.value)
            title = formate_file_name(media.file_name)
            size=get_size(media.file_size)
            f_caption = f"<code>{title}</code>"
            if CUSTOM_FILE_CAPTION:
                try:
                    f_caption=CUSTOM_FILE_CAPTION.format(file_name= '' if title is None else title, file_size='' if size is None else size, file_caption='')
                except:
                    return
            if STREAM_MODE == True:
                if msg.video or msg.document:
                    log_msg = msg
                    stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    button = [[
                        InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download),
                        InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream)
                    ],[
                        InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream))
                    ]]
                    reply_markup=InlineKeyboardMarkup(button)
            else:
                reply_markup = None
            del_msg = await msg.copy(chat_id=message.from_user.id, caption=f_caption, reply_markup=reply_markup, protect_content=False)
        else:
            del_msg = await msg.copy(chat_id=message.from_user.id, protect_content=False)
        if AUTO_DELETE_MODE == True:
            k = await client.send_message(chat_id=message.from_user.id, text=f"<b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nThis Movie File/Video will be deleted in <b><u>{AUTO_DELETE} minutes</u> 🫥 <i></b>(Due to Copyright Issues)</i>.\n\n<b><i>Please forward this File/Video to your Saved Messages and Start Download there</b>")
            await asyncio.sleep(AUTO_DELETE_TIME)
            try:
                await del_msg.delete()
            except:
                pass
            await k.edit_text("<b>Your File/Video is successfully deleted!!!</b>")
        return
    except:
        pass


@Client.on_message(filters.command("fsub") & filters.private)
async def fsub_handler(client, message):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    channels = await db.get_fsub_channels()
    enabled = await db.is_fsub_enabled()
    ch_list = "\n".join([f"  • <code>{ch}</code>" for ch in channels]) if channels else "  None"
    text = (
        f"<b>Force Subscribe Settings</b>\n\n"
        f"Status: <b>{'Enabled' if enabled else 'Disabled'}</b>\n"
        f"Channels ({len(channels)}):\n{ch_list}\n\n"
        f"<b>Commands:</b>\n"
        f"/fsub_add channel_id\n"
        f"/fsub_remove channel_id\n"
        f"/fsub_list\n"
        f"/fsub_on\n"
        f"/fsub_off"
    )
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("fsub_on") & filters.private)
async def fsub_on(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    await db.set_fsub_enabled(True)
    await message.reply_text("<b>Force Subscribe ENABLED!</b>", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("fsub_off") & filters.private)
async def fsub_off(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    await db.set_fsub_enabled(False)
    await message.reply_text("<b>Force Subscribe DISABLED!</b>", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("fsub_list") & filters.private)
async def fsub_list(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    channels = await db.get_fsub_channels()
    enabled = await db.is_fsub_enabled()
    if not channels:
        return await message.reply_text("<b>No channels added yet.</b>", parse_mode=enums.ParseMode.HTML)
    ch_list = "\n".join([f"{i+1}. <code>{ch}</code>" for i, ch in enumerate(channels)])
    await message.reply_text(
        f"<b>Force Sub Channels</b>\nStatus: {'ON' if enabled else 'OFF'}\n\n{ch_list}",
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command("fsub_add") & filters.private)
async def fsub_add(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    args = message.command
    if len(args) < 2:
        return await message.reply_text("<b>Usage: /fsub_add channel_id</b>", parse_mode=enums.ParseMode.HTML)
    try:
        ch_id = int(args[1])
    except ValueError:
        return await message.reply_text("<b>Invalid channel ID.</b>", parse_mode=enums.ParseMode.HTML)
    channels = await db.get_fsub_channels()
    if len(channels) >= 4:
        return await message.reply_text("<b>Max 4 channels allowed!</b>", parse_mode=enums.ParseMode.HTML)
    result = await db.add_fsub_channel(ch_id)
    if result:
        await message.reply_text(f"<b>Channel {ch_id} added!</b>", parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text(f"<b>Channel {ch_id} already exists!</b>", parse_mode=enums.ParseMode.HTML)


@Client.on_message(filters.command("fsub_remove") & filters.private)
async def fsub_remove(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    args = message.command
    if len(args) < 2:
        return await message.reply_text("<b>Usage: /fsub_remove channel_id</b>", parse_mode=enums.ParseMode.HTML)
    try:
        ch_id = int(args[1])
    except ValueError:
        return await message.reply_text("<b>Invalid channel ID.</b>", parse_mode=enums.ParseMode.HTML)
    result = await db.remove_fsub_channel(ch_id)
    if result:
        await message.reply_text(f"<b>Channel {ch_id} removed!</b>", parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text(f"<b>Channel {ch_id} not found!</b>", parse_mode=enums.ParseMode.HTML)


@Client.on_callback_query(filters.regex("^fsub_check$"))
async def fsub_check_callback(client, query):
    not_joined = await check_force_sub(client, query.from_user.id)
    if not_joined:
        kb = await get_fsub_buttons(client, not_joined)
        await query.answer("Join all channels first!", show_alert=True)
        await query.message.edit_reply_markup(kb)
    else:
        await query.answer("Verified! Click the file link again.", show_alert=True)
        await query.message.delete()


@Client.on_message(filters.command("add_banuser") & filters.private)
async def ban_user_handler(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    args = message.command
    if len(args) < 2:
        return await message.reply_text("<b>Usage: /add_banuser user_id</b>", parse_mode=enums.ParseMode.HTML)
    try:
        user_id = int(args[1])
    except ValueError:
        return await message.reply_text("<b>Invalid ID.</b>", parse_mode=enums.ParseMode.HTML)
    await db.ban_user(user_id)
    await message.reply_text(f"<b>User {user_id} BANNED!</b>", parse_mode=enums.ParseMode.HTML)
    try:
        await client.send_message(user_id, "<b>Banned.</b>", parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass


@Client.on_message(filters.command("del_banuser") & filters.private)
async def unban_user_handler(client, message):
    if message.from_user.id not in ADMINS:
        return await message.reply_text("<b>Not authorized.</b>", parse_mode=enums.ParseMode.HTML)
    args = message.command
    if len(args) < 2:
        return await message.reply_text("<b>Usage: /del_banuser user_id</b>", parse_mode=enums.ParseMode.HTML)
    try:
        user_id = int(args[1])
    except ValueError:
        return await message.reply_text("<b>Invalid ID.</b>", parse_mode=enums.ParseMode.HTML) 