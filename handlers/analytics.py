from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
import logging
from datetime import datetime, timezone, timedelta
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)
router = Router()


from utils.i18n import get_text, get_user_lang

async def get_analytics_keyboard(user_id: int):
    """Analytics klaviaturasi"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=await t("btn_analytics_keywords"), callback_data="analytics_top_keywords"),
                InlineKeyboardButton(text=await t("btn_analytics_companies"), callback_data="analytics_top_companies")
            ],
            [
                InlineKeyboardButton(text=await t("btn_analytics_salary"), callback_data="analytics_salary"),
                InlineKeyboardButton(text=await t("btn_analytics_locations"), callback_data="analytics_locations")
            ],
            [
                InlineKeyboardButton(text=await t("btn_analytics_today"), callback_data="analytics_today"),
                InlineKeyboardButton(text=await t("btn_analytics_general"), callback_data="analytics_general")
            ],
            [
                InlineKeyboardButton(text=await t("btn_close"), callback_data="close_analytics")
            ]
        ]
    )


from utils.i18n import get_msg_options

@router.message(F.text.in_(get_msg_options("menu_stats")))
async def cmd_analytics(message: Message):
    """Vakansiya statistikasi"""
    lang = await get_user_lang(message.from_user.id)
    async def t(key): return await get_text(key, lang=lang)
    
    await message.answer(
        await t("analytics_title") + "\n\n" + await t("analytics_text"),
        reply_markup=await get_analytics_keyboard(message.from_user.id),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "analytics_today")
async def analytics_today(callback: CallbackQuery):
    """Bugungi vakansiyalar"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
        
        async with db.pool.acquire() as conn:
            today = datetime.now(timezone.utc).date()
            
            # Bugungi vakansiyalar soni
            count = await conn.fetchval('''
                SELECT COUNT(*) FROM vacancies
                WHERE DATE(published_date) = $1
            ''', today)
            
            # Manbalar bo'yicha
            sources = await conn.fetch('''
                SELECT source, COUNT(*) as count
                FROM vacancies
                WHERE DATE(published_date) = $1
                GROUP BY source
                ORDER BY count DESC
            ''', today)
            
            text = await t("analytics_today_title")
            text += await t("analytics_total_new", count=count)
            
            if sources:
                text += await t("analytics_sources")
                for row in sources:
                    emoji = {'hh_uz': '🌐', 'telegram': '📱', 'user_post': '📢'}.get(row['source'], '🔗')
                    text += f"  {emoji} {row['source']}: {row['count']} ta\n"
            
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text=await t("btn_back"), callback_data="show_analytics")]
                        ]
                    ),
                    parse_mode='HTML'
                )
            except TelegramBadRequest:
                pass
            
    except Exception as e:
        logger.error(f"Analytics today error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)), show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "analytics_top_companies")
async def analytics_companies(callback: CallbackQuery):
    """Eng aktiv kompaniyalar"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
        
        async with db.pool.acquire() as conn:
            # Oxirgi 30 kundagi eng aktiv kompaniyalar
            companies = await conn.fetch('''
                SELECT company, COUNT(*) as count
                FROM vacancies
                WHERE published_date > NOW() - INTERVAL '30 days'
                AND company != 'Noma''lum'
                GROUP BY company
                ORDER BY count DESC
                LIMIT 10
            ''')
            
            text = await t("analytics_companies_title")
            text += await t("analytics_last_30_days")
            
            if companies:
                for i, row in enumerate(companies, 1):
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
                    text += f"{emoji} {row['company']}: <b>{row['count']}</b> ta\n"
            else:
                text += await t("analytics_no_data")
            
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text=await t("btn_back"), callback_data="show_analytics")]
                        ]
                    ),
                    parse_mode='HTML'
                )
            except TelegramBadRequest:
                pass
            
    except Exception as e:
        logger.error(f"Analytics companies error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)), show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "analytics_salary")
async def analytics_salary(callback: CallbackQuery):
    """Maosh statistikasi"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
        
        async with db.pool.acquire() as conn:
            # O'rtacha maosh
            avg_salary = await conn.fetchrow('''
                SELECT 
                    AVG(salary_min) as avg_min,
                    AVG(salary_max) as avg_max,
                    MIN(salary_min) as min_salary,
                    MAX(salary_max) as max_salary
                FROM vacancies
                WHERE salary_min IS NOT NULL
                AND published_date > NOW() - INTERVAL '30 days'
            ''')
            
            text = await t("analytics_salary_title")
            text += await t("analytics_last_30_days")
            
            if avg_salary and avg_salary['avg_min']:
                text += await t("analytics_avg_salary")
                text += await t("analytics_min", salary=f"{int(avg_salary['avg_min']):,}")
                text += await t("analytics_max", salary=f"{int(avg_salary['avg_max']):,}")
                
                text += await t("analytics_range")
                text += await t("analytics_lowest", salary=f"{int(avg_salary['min_salary']):,}")
                text += await t("analytics_highest", salary=f"{int(avg_salary['max_salary']):,}")
            else:
                text += await t("analytics_no_data")
            
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text=await t("btn_back"), callback_data="show_analytics")]
                        ]
                    ),
                    parse_mode='HTML'
                )
            except TelegramBadRequest:
                pass
            
    except Exception as e:
        logger.error(f"Analytics salary error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)), show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data == "analytics_top_keywords")
async def analytics_keywords(callback: CallbackQuery):
    """Eng ko'p qidirilgan so'zlar"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key): return await get_text(key, lang=lang)
        
        async with db.pool.acquire() as conn:
            # User filtrlaridan barcha keywordlarni yig'ish (sodda usul)
            filters = await conn.fetch("SELECT filter_data FROM users WHERE filter_data IS NOT NULL")
            
            import json
            from collections import Counter
            all_keywords = []
            for row in filters:
                try:
                    data = json.loads(row['filter_data'])
                    all_keywords.extend(data.get('keywords', []))
                except:
                    continue
            
            top_keywords = Counter(all_keywords).most_common(10)
            
            text = await t("analytics_keywords_title")
            if top_keywords:
                for i, (word, count) in enumerate(top_keywords, 1):
                    text += f"{i}. <b>{word}</b>: {count} marta\n" # 'marta' could be localized but likely acceptable
            else:
                text += await t("analytics_no_data")
            
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=await t("btn_back"), callback_data="show_analytics")]
                ]),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Analytics keywords error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)))
    await callback.answer()


@router.callback_query(F.data == "analytics_locations")
async def analytics_locations(callback: CallbackQuery):
    """Joylar bo'yicha statistika"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key): return await get_text(key, lang=lang)
        
        async with db.pool.acquire() as conn:
            locations = await conn.fetch('''
                SELECT location, COUNT(*) as count
                FROM vacancies
                WHERE location IS NOT NULL AND location != ''
                GROUP BY location
                ORDER BY count DESC
                LIMIT 10
            ''')
            
            text = await t("analytics_locations_title")
            if locations:
                for i, row in enumerate(locations, 1):
                    text += f"{i}. <b>{row['location']}</b>: {row['count']} ta vakansiya\n" # 'ta vakansiya' could be localized
            else:
                text += await t("analytics_no_data")
            
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=await t("btn_back"), callback_data="show_analytics")]
                ]),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Analytics locations error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)))
    await callback.answer()


@router.callback_query(F.data == "show_analytics")
@router.callback_query(F.data == "analytics_general")
async def show_analytics(callback: CallbackQuery):
    """Umumiy statistika"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key): return await get_text(key, lang=lang)
        
        await callback.message.edit_text(
            await t("analytics_title") + "\n\n" + await t("analytics_text"),
            reply_markup=await get_analytics_keyboard(user_id),
            parse_mode='HTML'
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "close_analytics")
async def close_analytics(callback: CallbackQuery):
    """Yopish"""
    await callback.message.delete()
    await callback.answer()