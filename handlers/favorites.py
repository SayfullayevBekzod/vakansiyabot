from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import db
import logging

logger = logging.getLogger(__name__)
router = Router()


from utils.i18n import get_text, get_user_lang

async def get_favorite_keyboard(user_id: int, vacancy_id: str):
    """Vakansiya uchun saqlash tugmasi"""
    lang = await get_user_lang(user_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=await get_text("btn_save", lang=lang),
                    callback_data=f"save_favorite_{vacancy_id}"
                ),
                InlineKeyboardButton(
                    text=await get_text("btn_full", lang=lang),
                    callback_data=f"view_full_{vacancy_id}"
                )
            ]
        ]
    )


async def get_saved_list_keyboard(user_id: int, page: int = 0, total_pages: int = 1):
    """Saqlangan vakansiyalar ro'yxati klaviaturasi"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    buttons = []
    
    # Navigatsiya
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text=await t("btn_prev"), callback_data=f"saved_page_{page-1}")
        )
    
    nav_buttons.append(
        InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="saved_info")
    )
    
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text=await t("btn_next"), callback_data=f"saved_page_{page+1}")
        )
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Boshqa tugmalar
    buttons.extend([
        [
            InlineKeyboardButton(text=await t("btn_clear_all"), callback_data="clear_all_favorites"),
            InlineKeyboardButton(text=await t("btn_refresh"), callback_data="refresh_favorites")
        ],
        [
            InlineKeyboardButton(text=await t("btn_close"), callback_data="close_favorites")
        ]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


from utils.i18n import get_msg_options

@router.message(F.text.in_(get_msg_options("menu_saved")))
async def cmd_favorites(message: Message):
    """Saqlangan vakansiyalar"""
    try:
        user_id = message.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
        
        # Saqlangan vakansiyalarni olish
        async with db.pool.acquire() as conn:
            favorites = await conn.fetch('''
                SELECT 
                    sv.vacancy_id,
                    sv.vacancy_title,
                    sv.sent_at,
                    v.title,
                    v.company,
                    v.location,
                    v.salary_min,
                    v.salary_max,
                    v.url,
                    v.source
                FROM sent_vacancies sv
                LEFT JOIN vacancies v ON sv.vacancy_id = v.vacancy_id
                WHERE sv.user_id = $1
                ORDER BY sv.sent_at DESC
                LIMIT 5
            ''', user_id)
            
            total = await conn.fetchval('SELECT COUNT(*) FROM sent_vacancies WHERE user_id = $1', user_id)
            total_pages = (total + 4) // 5
        
        if not favorites:
            await message.answer(await t("fav_empty"), parse_mode='HTML')
            return
        
        text = await t("fav_title", total=total)
        
        for i, fav in enumerate(favorites, 1):
            title = fav['title'] or fav['vacancy_title'] or await t("default_job_title")
            company = fav['company'] or await t("default_company")
            location = fav['location'] or await t("default_location")
            
            text += f"{i}. <b>{title}</b>\n"
            text += f"   🏢 {company}\n"
            text += f"   📍 {location}\n"
            text += f"   🔗 /view_{fav['vacancy_id']}\n\n"
        
        await message.answer(
            text,
            reply_markup=await get_saved_list_keyboard(user_id, 0, total_pages),
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Favorites error: {e}", exc_info=True)
        await message.answer(await get_text("msg_error_generic", lang=await get_user_lang(message.from_user.id)))


@router.callback_query(F.data.startswith("save_favorite_"))
async def save_favorite(callback: CallbackQuery):
    """Vakansiyani saqlash"""
    try:
        vacancy_id = callback.data.replace("save_favorite_", "")
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        
        # Saqlash
        success = await db.add_sent_vacancy(
            user_id, 
            vacancy_id, 
            "Saved by user"
        )
        
        if success:
            await callback.answer(await get_text("fav_saved", lang=lang), show_alert=True)
            logger.info(f"User {user_id} saved vacancy {vacancy_id}")
        else:
            await callback.answer(await get_text("fav_already", lang=lang), show_alert=True)
            
    except Exception as e:
        logger.error(f"Save favorite error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)), show_alert=True)


@router.callback_query(F.data.startswith("unsave_favorite_"))
async def unsave_favorite(callback: CallbackQuery):
    """Vakansiyani o'chirish"""
    try:
        vacancy_id = callback.data.replace("unsave_favorite_", "")
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        
        async with db.pool.acquire() as conn:
            await conn.execute('''
                DELETE FROM sent_vacancies
                WHERE user_id = $1 AND vacancy_id = $2
            ''', user_id, vacancy_id)
        
        await callback.answer(await get_text("fav_deleted", lang=lang), show_alert=True)
        
        # Ro'yxatni yangilash
        await refresh_favorites(callback)
        
    except Exception as e:
        logger.error(f"Unsave favorite error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)), show_alert=True)


@router.callback_query(F.data == "clear_all_favorites")
async def clear_all_favorites(callback: CallbackQuery):
    """Hammasini o'chirish"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=await t("btn_confirm_delete"), callback_data="confirm_clear_favorites"),
                InlineKeyboardButton(text=await t("btn_cancel"), callback_data="refresh_favorites")
            ]
        ]
    )
    
    await callback.message.edit_text(
        await t("fav_clear_confirm"),
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_clear_favorites")
async def confirm_clear_favorites(callback: CallbackQuery):
    """Tozalashni tasdiqlash"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        
        async with db.pool.acquire() as conn:
            await conn.execute('''
                DELETE FROM sent_vacancies
                WHERE user_id = $1
            ''', user_id)
        
        await callback.message.edit_text(
            await get_text("fav_cleared", lang=lang),
            parse_mode='HTML'
        )
        await callback.answer(await get_text("fav_deleted", lang=lang), show_alert=True)
        
    except Exception as e:
        logger.error(f"Clear favorites error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)), show_alert=True)


@router.callback_query(F.data == "refresh_favorites")
async def refresh_favorites(callback: CallbackQuery):
    """Yangilash"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
        
        async with db.pool.acquire() as conn:
            favorites = await conn.fetch('''
                SELECT sv.vacancy_id, sv.vacancy_title, v.title, v.company, v.location, v.salary_min, v.salary_max
                FROM sent_vacancies sv
                LEFT JOIN vacancies v ON sv.vacancy_id = v.vacancy_id
                WHERE sv.user_id = $1
                ORDER BY sv.sent_at DESC
                LIMIT 5
            ''', user_id)
            
            total = await db.pool.fetchval('SELECT COUNT(*) FROM sent_vacancies WHERE user_id = $1', user_id)
            total_pages = (total + 4) // 5
        
        if not favorites:
            await callback.message.edit_text(
                await t("fav_empty"),
                parse_mode='HTML'
            )
            return
        
        text = await t("fav_title", total=total)
        
        for i, fav in enumerate(favorites, 1):
            title = fav['title'] or fav['vacancy_title'] or await t("default_job_title")
            company = fav['company'] or await t("default_company")
            text += f"{i}. <b>{title}</b>\n   🏢 {company}\n   🔗 /view_{fav['vacancy_id']}\n\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=await get_saved_list_keyboard(user_id, 0, total_pages),
            parse_mode='HTML'
        )
        await callback.answer(await t("fav_updated"))
    except Exception as e:
        logger.error(f"Refresh favorites error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)), show_alert=True)


@router.callback_query(F.data.startswith("saved_page_"))
async def saved_page(callback: CallbackQuery):
    """Sahifani almashtirish"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
        
        page = int(callback.data.replace("saved_page_", ""))
        async with db.pool.acquire() as conn:
            favorites = await conn.fetch('''
                SELECT sv.vacancy_id, sv.vacancy_title, v.title, v.company, v.location, v.salary_min, v.salary_max
                FROM sent_vacancies sv
                LEFT JOIN vacancies v ON sv.vacancy_id = v.vacancy_id
                WHERE sv.user_id = $1
                ORDER BY sv.sent_at DESC
                LIMIT 5 OFFSET $2
            ''', user_id, page * 5)
            total = await db.pool.fetchval('SELECT COUNT(*) FROM sent_vacancies WHERE user_id = $1', user_id)
            total_pages = (total + 4) // 5
        
        if not favorites:
            await callback.answer(await t("fav_no_more"))
            return
            
        text = await t("fav_title", total=total)
        for i, fav in enumerate(favorites, page * 5 + 1):
            title = fav['title'] or fav['vacancy_title'] or await t("default_job_title")
            company = fav['company'] or await t("default_company")
            text += f"{i}. <b>{title}</b>\n   🏢 {company}\n   🔗 /view_{fav['vacancy_id']}\n\n"
            
        await callback.message.edit_text(text, reply_markup=await get_saved_list_keyboard(user_id, page, total_pages), parse_mode='HTML')
        await callback.answer()
    except Exception as e:
        logger.error(f"saved_page error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)))


@router.callback_query(F.data.startswith("view_full_"))
async def view_full_saved(callback: CallbackQuery):
    """Saqlangan vakansiyani to'liq ko'rish"""
    try:
        user_id = callback.from_user.id
        lang = await get_user_lang(user_id)
        async def t(key): return await get_text(key, lang=lang)
        
        vacancy_id = callback.data.replace("view_full_", "")
        vac = await db.get_vacancy(vacancy_id)
        if not vac:
            await callback.answer(await t("fav_not_found"), show_alert=True)
            return
            
        from filters import vacancy_filter
        text = vacancy_filter.format_vacancy_message(vac, lang=lang)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=await t("btn_delete"), callback_data=f"unsave_favorite_{vacancy_id}")],
            [InlineKeyboardButton(text=await t("btn_back_list"), callback_data="refresh_favorites")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
        await callback.answer()
    except Exception as e:
        logger.error(f"view_full_saved error: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=await get_user_lang(callback.from_user.id)))


@router.callback_query(F.data == "close_favorites")
async def close_favorites(callback: CallbackQuery):
    """Yopish"""
    await callback.message.delete()
    await callback.answer()