from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from database import db
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta
from utils.i18n import get_text, get_user_lang, get_msg_options

logger = logging.getLogger(__name__)
router = Router()


# Referral mukofotlar - YANGILANGAN (5, 10, 20, 30)
REFERRAL_REWARDS = {
    '5': {'days': 3, 'title': '5 ta do\'st'},
    '10': {'days': 6, 'title': '10 ta do\'st'},
    '20': {'days': 12, 'title': '20 ta do\'st'},
    '30': {'days': 30, 'title': '30 ta do\'st'},
}


async def get_referral_keyboard(user_id: int, bot: Bot):
    """Referral klaviaturasi"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
    share_text = await t("ref_share_text")
    
    # URL encoding for parameters
    encoded_ref_link = urllib.parse.quote(ref_link)
    encoded_text = urllib.parse.quote(share_text)
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=await t("btn_share"),
                    url=f"https://t.me/share/url?url={encoded_ref_link}&text={encoded_text}"
                )
            ],
            [
                InlineKeyboardButton(text=await t("btn_my_stats"), callback_data="referral_stats"),
                InlineKeyboardButton(text=await t("btn_leaderboard"), callback_data="referral_leaderboard")
            ],
            [InlineKeyboardButton(text=await t("btn_back"), callback_data="close_referral")]
        ]
    )


@router.message(F.text.in_(get_msg_options("menu_referral")))
async def cmd_referral(message: Message, user_id: int = None):
    """Referral sistema"""
    if user_id is None:
        user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    # Referral statistika
    stats = await db.get_referral_stats(user_id)
    ref_count = stats['total']
    premium_refs = stats['premium']
    
    me = await message.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"
    
    premium_info = ""
    if premium_refs > 0:
        premium_info = await t("ref_premium_info", premium=premium_refs)
    
    text = await t("ref_title") + "\n\n"
    text += await t("ref_desc", total=ref_count, premium_info=premium_info) + "\n\n"
    
    text += await t("ref_rewards_title") + "\n"
    for count_str, reward in sorted(REFERRAL_REWARDS.items(), key=lambda x: int(x[0])):
        count = int(count_str)
        if ref_count >= count:
            status = "✅"
        elif ref_count >= count - 2:
            status = "⏳"
        else:
            status = "🔒"
        
        text += await t("ref_reward_item", status=status, title=reward['title'], days=reward['days']) + "\n"
        if status == "⏳":
            text += await t("ref_reward_remaining", count=count - ref_count) + "\n"
    
    text += f"\n" + await t("ref_link_title") + f"\n<code>{ref_link}</code>\n\n"
    text += await t("ref_footer")
    
    await message.answer(
        text,
        reply_markup=await get_referral_keyboard(user_id, message.bot),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "referral_stats")
async def referral_stats(callback: CallbackQuery):
    """Referral statistika"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    referrals = await db.get_referral_list(user_id, limit=20)
    
    if not referrals:
        text = await t("ref_stats_title") + "\n\n" + await t("ref_no_referrals")
    else:
        text = await t("ref_stats_title") + " " + await t("ref_list_header")
        for i, ref in enumerate(referrals, 1):
            name = ref['first_name']
            username = f" @{ref['username']}" if ref['username'] else ""
            date = ref['created_at'].strftime('%d.%m.%Y')
            status = "💎" if ref['is_premium'] else "🆓"
            text += f"{i}. {status} {name}{username} - {date}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=await t("btn_back"), callback_data="show_referral")]]
        ),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "referral_leaderboard")
async def referral_leaderboard(callback: CallbackQuery):
    """Top referrallar"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    top = await db.get_top_referrers(10)
    
    text = await t("ref_leaderboard_title") + "\n\n"
    if not top:
        text += await t("ref_no_leaderboard")
    else:
        for i, user in enumerate(top, 1):
            emoji = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "👤"))
            text += f"{emoji} {i}. {user['first_name']} - <b>{user['total']}</b> ta\n"
    
    text += await t("ref_leaderboard_footer")
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=await t("btn_back"), callback_data="show_referral")]
        ]),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "show_referral")
async def show_referral(callback: CallbackQuery):
    """Referral sahifasini qayta ko'rsatish"""
    await cmd_referral(callback.message, user_id=callback.from_user.id)
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "close_referral")
async def close_referral(callback: CallbackQuery):
    """Yopish"""
    await callback.message.delete()
    await callback.answer()


# Referral link orqali start
async def process_referral_start(message: Message, referrer_id: int):
    """Referral link orqali kelgan foydalanuvchi"""
    user_id = message.from_user.id
    if user_id == referrer_id: return
    
    user = await db.get_user(user_id)
    if user and user.get('referred_by'): return
    
    # Referrerni saqlash
    try:
        current_ref = await db.get_user_referrer(user_id)
        if current_ref:
            logger.info(f"User {user_id} already has referrer: {current_ref}")
            return
            
        success = await db.set_user_referrer(user_id, referrer_id)
        if not success:
            logger.error(f"Failed to set referrer for {user_id}")
            return
            
        # Yangi statistika
        stats = await db.get_referral_stats(referrer_id)
        ref_count = stats['total']
        logger.info(f"Referral successful: {referrer_id} -> {user_id}. Total for referrer: {ref_count}")
    except Exception as e:
        logger.error(f"Error in process_referral_start (DB part): {e}")
        return
    
    # Referrerga xabar
    try:
        ref_lang = await get_user_lang(referrer_id)
        btn_text = await get_text("menu_referral", lang=ref_lang)
        alert_text = await get_text("ref_new_alert", lang=ref_lang, name=message.from_user.first_name, total=ref_count, btn=btn_text)
        
        await message.bot.send_message(
            referrer_id,
            alert_text,
            parse_mode='HTML'
        )
    except: pass
    
    # Mukofot tekshirish
    for count_str, reward in REFERRAL_REWARDS.items():
        if ref_count == int(count_str):
            days = reward['days']
            if await db.set_premium(referrer_id, days):
                try:
                    ref_lang = await get_user_lang(referrer_id)
                    reward_alert = await get_text("ref_reward_alert", lang=ref_lang, title=reward['title'], days=days)
                    await message.bot.send_message(
                        referrer_id,
                        reward_alert,
                        parse_mode='HTML'
                    )
                except: pass
            break
