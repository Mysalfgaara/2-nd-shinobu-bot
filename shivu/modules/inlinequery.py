import re
import time
import html
import logging
from telegram import Update, InlineQueryResultPhoto, InlineQueryResultCachedPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import InlineQueryHandler, CallbackQueryHandler, CallbackContext
from html import escape
from cachetools import TTLCache
from pymongo import ASCENDING
from shivu import user_collection, collection, application, db

# Setup MongoDB indexes
def setup_indexes():
    db.characters.create_index([('id', ASCENDING)])
    db.characters.create_index([('anime', ASCENDING)])
    db.characters.create_index([('img_url', ASCENDING)])
    db.user_collection.create_index([('characters.id', ASCENDING)])
    db.user_collection.create_index([('characters.name', ASCENDING)])
    db.user_collection.create_index([('characters.img_url', ASCENDING)])

setup_indexes()

# Setup caching
all_characters_cache = TTLCache(maxsize=10000, ttl=36000)
user_collection_cache = TTLCache(maxsize=10000, ttl=60)

# Tag mappings
tag_mappings = {
    '👘': '👘𝑲𝒊𝒎𝒐𝒏𝒐👘',
    '☃️': '☃️𝑾𝒊𝒏𝒕𝒆𝒓☃️',
    '🐰': '🐰𝑩𝒖𝒏𝒏𝒚🐰',
    '🎮': '🎮𝑮𝒂𝒎𝒆🎮',
    '🎄': '🎄𝑪𝒓𝒊𝒔𝒕𝒎𝒂𝒔🎄',
    '🎃': '🎃𝑯𝒆𝒍𝒍𝒐𝒘𝒆𝒆𝒏🎃',
    '🏖️': '🏖️𝑺𝒖𝒎𝒎𝒆𝒓🏖️',
    '🧹': '🧹𝑴𝒂𝒅𝒆🧹',
    '🥻': '🥻𝑺𝒂𝒓𝒆𝒆🥻',
    '☔': '☔𝑴𝒐𝒏𝒔𝒐𝒐𝒏☔',
    '🎒': '🎒𝑺𝒄𝒉𝒐𝒐𝒍🎒',
    '🎩': '🎩𝑻𝒖𝒙𝒆𝒅𝒐🎩',
    '👥': '👥𝐃𝐮𝐨👥',
    '🤝🏻': '🤝🏻𝐆𝐫𝐨𝐮𝐩🤝🏻',
    '👑': '👑𝑳𝒐𝒓𝒅👑',
    '🩺': '🩺𝑵𝒖𝒓𝒔𝒆🩺',
    '💍': '💍𝑾𝒆𝒅𝒅𝒊𝒏𝒈💍',
    '🎊': '🎊𝑪𝒉𝒆𝒆𝒓𝒍𝒆𝒂𝒅𝒆𝒓𝒔🎊',
    '⚽': '⚽𝑺𝒐𝒄𝒄𝒆𝒓⚽',
    '🏀': '🏀𝑩𝒂𝒔𝒌𝒆𝒕𝒃𝒂𝒍𝒍🏀 ',
    '💐': '💐𝑮𝒓𝒐𝒐𝒎💐',
    '🥂': '🥂𝑷𝒂𝒓𝒕𝒚🥂',
    '💞': '💞𝑽𝒂𝒍𝒆𝒏𝒕𝒊𝒏𝒆💞',
}

async def inlinequery(update: Update, context: CallbackContext) -> None:
    query_text = update.inline_query.query
    offset = int(update.inline_query.offset) if update.inline_query.offset else 0

    # Determine search mode
    if query_text.startswith('collection.'):
        # Search inside a user's collection
        user_id_str, *search_terms = query_text.split(' ')[0].split('.')[1], ' '.join(query_text.split(' ')[1:])
        if user_id_str.isdigit():
            user_id = int(user_id_str)
            user = user_collection_cache.get(user_id) or await user_collection.find_one({'id': user_id})
            if user:
                user_collection_cache[user_id] = user
            all_characters = list({v['id']: v for v in user.get('characters', [])}.values()) if user else []
            if search_terms:
                regex = re.compile(re.escape(' '.join(search_terms)), re.IGNORECASE)
                all_characters = [
                    c for c in all_characters
                    if any(regex.search(str(c[field])) for field in ('name', 'rarity', 'id', 'anime'))
                ]
        else:
            all_characters = []
    else:
        # Search in all characters
        if query_text:
            regex = re.compile(re.escape(query_text), re.IGNORECASE)
            all_characters = list(
                await collection.find({
                    "$or": [
                        {"name": regex},
                        {"rarity": regex},
                        {"id": regex},
                        {"anime": regex}
                    ]
                }).to_list(length=None)
            )
        else:
            all_characters = all_characters_cache.get('all_characters') or list(await collection.find({}).to_list(length=None))
            all_characters_cache['all_characters'] = all_characters

    # Pagination
    characters = all_characters[offset:offset + 50]
    has_more = len(all_characters) > offset + 50
    next_offset = str(offset + 50) if has_more else ''

    results = []
    for character in characters:
        anime_characters = await collection.count_documents({'anime': character['anime']})

        if query_text.startswith('collection.'):
            user_character_count = sum(c['id'] == character['id'] for c in user.get('characters', []))
            user_anime_characters = sum(c['anime'] == character['anime'] for c in user.get('characters', []))
            caption = (
                f"<b>Lᴏᴏᴋ Aᴛ <a href='tg://user?id={user['id']}'>{escape(user.get('first_name', user['id']))}</a>'s Waifu....!!</b>\n\n"
                f"<b>{character['id']}:</b> {character['name']} x{user_character_count}\n"
                f"<b>{character['anime']}</b> {user_anime_characters}/{anime_characters}\n"
                f"﹙<b>{character['rarity'][0]} 𝙍𝘼𝙍𝙄𝙏𝙔:</b> {character['rarity'][2:]}﹚\n"
            )
        else:
            caption = (
                f"<b>Lᴏᴏᴋ Aᴛ Tʜɪs Waifu....!!</b>\n\n"
                f"<b>{character['id']}:</b> {character['name']}\n"
                f"<b>{character['anime']}</b>\n"
                f"﹙<b>{character['rarity'][0]} 𝙍𝘼𝙍𝙄𝙏𝙔:</b> {character['rarity'][2:]}﹚\n"
            )

        # Append special tags if present
        for tag, description in tag_mappings.items():
            if tag in character['name']:
                caption += f"\n\n{description}"
                break

        # Inline keyboard for Top 10 grabbers
        keyboard = [[InlineKeyboardButton("ᴛᴏᴘ 𝟷𝟶 ɢʀᴀʙʙᴇʀs", callback_data=f'top10_grabbers_{character["id"]}')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        img_url = character['img_url']
        if img_url.startswith("http"):
            # Works for Catbox and normal URLs
            results.append(
                InlineQueryResultPhoto(
                    id=f"{character['id']}_{time.time()}",
                    photo_url=img_url,
                    thumbnail_url=img_url,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            )
        else:
            # Telegram cached file_id
            results.append(
                InlineQueryResultCachedPhoto(
                    id=f"{character['id']}_{time.time()}",
                    photo_file_id=img_url,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            )

    await update.inline_query.answer(results, next_offset=next_offset, cache_time=5)

# Top 10 grabbers callback
async def top10_grabbers_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    try:
        character_id = query.data.split('_')[2]
    except IndexError:
        await query.edit_message_text("Invalid callback data format.", parse_mode='HTML')
        return

    try:
        top_grabbers = await user_collection.aggregate([
            {'$match': {'characters.id': character_id}},
            {'$unwind': '$characters'},
            {'$match': {'characters.id': character_id}},
            {'$group': {'_id': '$id', 'username': {'$first': '$username'}, 'first_name': {'$first': '$first_name'}, 'character_count': {'$sum': 1}}},
            {'$sort': {'character_count': -1}},
            {'$limit': 10}
        ]).to_list(length=10)

        if top_grabbers:
            grabbers_text = "<b>🥇 ᴛᴏᴘ 𝟷𝟶 ɢʀᴀʙʙᴇʀs ᴏғ ᴛʜɪs ᴡᴀɪғᴜ: 🍃</b>\n\n"
            for i, user in enumerate(top_grabbers, start=1):
                username = user.get('username')
                first_name = html.escape(user.get('first_name', 'Unknown') or 'Unknown')
                if len(first_name) > 10:
                    first_name = first_name[:10] + '...'
                link = f'<a href="https://t.me/{username}"><b>{first_name}</b></a>' if username else f'<b>{first_name}</b>'
                grabbers_text += f"{i}. {link} ➾ <b>{user.get('character_count', 0)}</b>\n"
        else:
            grabbers_text = "<b>ɴᴏ ɢʀᴀʙʙᴇs ғᴏᴜɴᴅ ғᴏʀ ᴛʜɪs ᴄʜᴀʀᴀᴄᴛᴇʀ..⁉️</b>."

    except Exception as e:
        grabbers_text = f"An error occurred while fetching top grabbers: {e}"

    await query.edit_message_text(grabbers_text, parse_mode='HTML')

# Add handlers
application.add_handler(CallbackQueryHandler(top10_grabbers_callback, pattern=r'^top10_grabbers_'))
application.add_handler(InlineQueryHandler(inlinequery, block=False))
