from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
from filters import vacancy_filter
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
router = Router()


def calculate_match_score(vacancy: dict, user_profile: dict) -> int:
    """Vakansiya va foydalanuvchi o'rtasidagi match %"""
    score = 0
    max_score = 100
    
    # Keywords match (40%)
    user_keywords = user_profile.get('keywords', [])
    if user_keywords:
        vac_text = f"{vacancy.get('title', '')} {vacancy.get('description', '')}".lower()
        matched_keywords = sum(1 for kw in user_keywords if kw.lower() in vac_text)
        score += int((matched_keywords / len(user_keywords)) * 40)
    else:
        score += 20  # Default if no keywords
    
    # Location match (20%)
    user_locations = user_profile.get('locations', [])
    vac_location = vacancy.get('location', '').lower()
    if user_locations:
        location_match = any(loc.lower() in vac_location for loc in user_locations)
        if location_match:
            score += 20
    else:
        score += 10
    
    # Salary match (20%)
    user_salary_min = user_profile.get('salary_min')
    vac_salary_min = vacancy.get('salary_min')
    vac_salary_max = vacancy.get('salary_max')
    
    if user_salary_min and (vac_salary_min or vac_salary_max):
        if vac_salary_max and vac_salary_max >= user_salary_min:
            score += 20
        elif vac_salary_min and vac_salary_min >= user_salary_min * 0.8:
            score += 15
    else:
        score += 10
    
    # Experience match (20%)
    user_exp = user_profile.get('experience_level')
    vac_exp = vacancy.get('experience_level')
    
    if user_exp and vac_exp:
        if user_exp == vac_exp:
            score += 20
        elif user_exp in ['between_1_and_3', 'between_3_and_6'] and vac_exp == 'not_specified':
            score += 15
    else:
        score += 10
    
    return min(score, max_score)


def get_match_emoji(score: int) -> str:
    """Match %ga qarab emoji"""
    if score >= 90:
        return "🔥"
    elif score >= 75:
        return "⭐️"
    elif score >= 60:
        return "✨"
    elif score >= 50:
        return "💫"
    else:
        return "📌"


from utils.i18n import get_text, get_user_lang

async def get_smart_keyboard(user_id: int):
    """Smart matching klaviaturasi"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=await t("smart_btn_best"), callback_data="smart_best_match"),
                InlineKeyboardButton(text=await t("smart_btn_top10"), callback_data="smart_top_10")
            ],
            [
                InlineKeyboardButton(text=await t("smart_btn_ai_analysis"), callback_data="ai_skill_gap")
            ],
            [
                InlineKeyboardButton(text=await t("smart_btn_profile"), callback_data="smart_profile"),
                InlineKeyboardButton(text=await t("smart_btn_settings"), callback_data="smart_settings")
            ],
            [
                InlineKeyboardButton(text=await t("btn_back"), callback_data="close_smart")
            ]
        ]
    )


from utils.i18n import get_msg_options

@router.message(F.text.in_(get_msg_options("menu_smart")))
async def cmd_smart_matching(message: Message):
    """Smart matching asosiy sahifa"""
    # Premium tekshirish
    is_premium = await db.is_premium(message.from_user.id)
    lang = await get_user_lang(message.from_user.id)
    
    if not is_premium:
        title = await get_text("smart_premium_title", lang=lang)
        desc = await get_text("smart_premium_desc", lang=lang)
        await message.answer(f"{title}\n\n{desc}", parse_mode='HTML')
        return
    
    # User profili
    user_filter = await db.get_user_filter(message.from_user.id)
    
    if not user_filter or not user_filter.get('keywords'):
        await message.answer(await get_text("smart_no_profile", lang=lang), parse_mode='HTML')
        return
    
    # Profile completeness
    completeness = 0
    if user_filter.get('keywords'):
        completeness += 30
    if user_filter.get('locations'):
        completeness += 20
    if user_filter.get('salary_min'):
        completeness += 20
    if user_filter.get('experience_level'):
        completeness += 30
    
    text = await get_text("smart_intro_title", lang=lang) + "\n\n"
    
    comp_text = await get_text("smart_completeness", lang=lang)
    text += f"{comp_text.format(percent=completeness)}\n"
    
    if completeness < 100:
        text += await get_text("smart_tip_fill", lang=lang) + "\n"
    text += "\n"
    
    text += await get_text("smart_what_is", lang=lang) + "\n\n"
    
    text += await get_text("smart_choose", lang=lang)
    
    await message.answer(
        text,
        reply_markup=await get_smart_keyboard(message.from_user.id),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "smart_best_match")
async def smart_best_match(callback: CallbackQuery):
    """Eng mos vakansiyalar"""
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(await get_text("smart_searching", lang=lang), parse_mode='HTML')
    
    try:
        # User profili
        user_filter = await db.get_user_filter(callback.from_user.id)
        
        # Vakansiyalarni olish (oxirgi 7 kun)
        async with db.pool.acquire() as conn:
            vacancies = await conn.fetch('''
                SELECT * FROM vacancies
                WHERE published_date > NOW() - INTERVAL '7 days'
                ORDER BY published_date DESC
                LIMIT 100
            ''')
        
        if not vacancies:
            await callback.message.edit_text(await get_text("smart_no_results", lang=lang), parse_mode='HTML')
            return
        
        # Match score hisoblash
        scored_vacancies = []
        for vac in vacancies:
            vac_dict = dict(vac)
            score = calculate_match_score(vac_dict, user_filter)
            vac_dict['match_score'] = score
            scored_vacancies.append(vac_dict)
        
        # Saralash (yuqoridan pastga)
        scored_vacancies.sort(key=lambda x: x['match_score'], reverse=True)
        
        # Top 5 ni ko'rsatish
        text = await get_text("smart_results_title", lang=lang) + "\n\n"
        
        for i, vac in enumerate(scored_vacancies[:5], 1):
            score = vac['match_score']
            emoji = get_match_emoji(score)
            
            text += f"{i}. {emoji} <b>{vac['title']}</b>\n"
            text += f"   Match: <b>{score}%</b>\n"
            text += f"   🏢 {vac['company']}\n"
            text += f"   📍 {vac['location']}\n"
            
            if vac['salary_min'] or vac['salary_max']:
                salary = ""
                if vac['salary_min']:
                    salary = f"{vac['salary_min']:,}"
                if vac['salary_max']:
                    salary += f" - {vac['salary_max']:,}"
                text += f"   💰 {salary} so'm\n"
            
            text += f"   🔗 {vac['url']}\n\n"
        
        text += await get_text("smart_results_hint", lang=lang)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=await get_text("smart_btn_top10", lang=lang), callback_data="smart_top_10")],
                [InlineKeyboardButton(text=await get_text("btn_back", lang=lang), callback_data="show_smart")]
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Smart matching error: {e}", exc_info=True)
        await callback.message.edit_text(await get_text("msg_error_generic", lang=lang), parse_mode='HTML')
    
    await callback.answer()


@router.callback_query(F.data == "smart_top_10")
async def smart_top_10(callback: CallbackQuery):
    """Top 10 vakansiyalar (qisqacha)"""
    lang = await get_user_lang(callback.from_user.id)
    try:
        user_filter = await db.get_user_filter(callback.from_user.id)
        
        async with db.pool.acquire() as conn:
            vacancies = await conn.fetch('''
                SELECT * FROM vacancies
                WHERE published_date > NOW() - INTERVAL '7 days'
                ORDER BY published_date DESC
                LIMIT 100
            ''')
        
        # Scoring
        scored_vacancies = []
        for vac in vacancies:
            vac_dict = dict(vac)
            score = calculate_match_score(vac_dict, user_filter)
            vac_dict['match_score'] = score
            scored_vacancies.append(vac_dict)
        
        scored_vacancies.sort(key=lambda x: x['match_score'], reverse=True)
        
        # Top 10
        text = await get_text("smart_top10_title", lang=lang) + "\n\n"
        
        for i, vac in enumerate(scored_vacancies[:10], 1):
            score = vac['match_score']
            emoji = get_match_emoji(score)
            
            text += f"{i}. {emoji} <b>{score}%</b> - {vac['title'][:40]}\n"
            text += f"   🏢 {vac['company'][:30]}\n\n"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=await get_text("smart_btn_details", lang=lang), callback_data="smart_best_match")],
                [InlineKeyboardButton(text=await get_text("btn_back", lang=lang), callback_data="show_smart")]
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Top 10 error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=lang), show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "smart_profile")
async def smart_profile(callback: CallbackQuery):
    """Foydalanuvchi profili"""
    lang = await get_user_lang(callback.from_user.id)
    user_filter = await db.get_user_filter(callback.from_user.id)
    
    if not user_filter:
        await callback.message.edit_text(
            await get_text("smart_profile_empty", lang=lang),
            parse_mode='HTML'
        )
        return
    
    # Profile analysis
    completeness = 0
    missing = []
    
    if user_filter.get('keywords'):
        completeness += 30
    else:
        missing.append(await get_text("settings_lbl_keywords", lang=lang))
    
    if user_filter.get('locations'):
        completeness += 20
    else:
        missing.append(await get_text("settings_lbl_locations", lang=lang))
    
    if user_filter.get('salary_min'):
        completeness += 20
    else:
        missing.append(await get_text("settings_lbl_salary", lang=lang))
    
    if user_filter.get('experience_level'):
        completeness += 30
    else:
        missing.append(await get_text("settings_lbl_experience", lang=lang))
    
    text = await get_text("smart_profile_title", lang=lang) + "\n\n"
    
    comp_text = await get_text("smart_completeness", lang=lang)
    text += f"{comp_text.format(percent=completeness)}\n\n"
    
    if completeness == 100:
        text += await get_text("smart_profile_complete", lang=lang) + "\n\n"
    else:
        text += await get_text("smart_profile_missing", lang=lang) + "\n"
        for item in missing:
            text += f"  • {item}\n"
        text += f"\n{await get_text('smart_profile_tip', lang=lang)}\n\n"
    
    # Current settings
    text += await get_text("smart_settings_current", lang=lang) + "\n"
    if user_filter.get('keywords'):
        text += f"🔑 {', '.join(user_filter['keywords'][:3])}\n"
    if user_filter.get('locations'):
        text += f"📍 {', '.join(user_filter['locations'])}\n"
    if user_filter.get('salary_min'):
        text += f"💰 {await get_text('settings_val_from', lang=lang)} {user_filter['salary_min']:,} so'm\n"
    if user_filter.get('experience_level'):
        exp_level = user_filter['experience_level']
        exp_text = await get_text(f"exp_{exp_level}", lang=lang)
        text += f"👔 {exp_text}\n"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await get_text("smart_btn_settings", lang=lang), callback_data="smart_settings")],
            [InlineKeyboardButton(text=await get_text("btn_back", lang=lang), callback_data="show_smart")]
        ]
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data == "smart_settings")
async def smart_settings(callback: CallbackQuery):
    """Sozlamalar"""
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(
        await get_text("smart_settings_page", lang=lang),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=await get_text("btn_back", lang=lang), callback_data="show_smart")]
            ]
        ),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "show_smart")
async def show_smart(callback: CallbackQuery):
    """Smart matching sahifasi"""
    await cmd_smart_matching(callback.message)
    await callback.answer()


@router.callback_query(F.data == "close_smart")
async def close_smart(callback: CallbackQuery):
    """Yopish"""
    await callback.message.delete()
    await callback.answer()