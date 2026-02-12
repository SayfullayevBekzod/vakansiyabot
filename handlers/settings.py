from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
import logging

logger = logging.getLogger(__name__)

router = Router()


# FSM States
class SettingsStates(StatesGroup):
    waiting_for_keywords = State()
    waiting_for_locations = State()
    waiting_for_min_salary = State()
    waiting_for_max_salary = State()


from utils.i18n import get_text, get_user_lang

async def get_settings_keyboard(is_premium: bool = False, user_id: int = None):
    """Sozlamalar klaviaturasi"""
    lang = await get_user_lang(user_id) if user_id else 'uz'
    
    # helper
    async def t(key): return await get_text(key, lang=lang)

    buttons = [
        [
            InlineKeyboardButton(text=await t("settings_btn_keywords"), callback_data="set_keywords"),
            InlineKeyboardButton(text=await t("settings_btn_locations"), callback_data="set_locations")
        ],
        [
            InlineKeyboardButton(text=await t("settings_btn_salary"), callback_data="set_salary"),
            InlineKeyboardButton(text=await t("settings_btn_experience"), callback_data="set_experience")
        ],
        [
            InlineKeyboardButton(text=await t("settings_btn_sources"), callback_data="set_sources"),
            InlineKeyboardButton(text="🇺🇿/🇷🇺/🇺🇸 Language", callback_data="set_language")
        ],
        [
            InlineKeyboardButton(text=await t("settings_btn_current"), callback_data="show_current_settings")
        ],
        [
            InlineKeyboardButton(text=await t("settings_btn_role"), callback_data="set_role")
        ],
        [
            InlineKeyboardButton(text=await t("settings_btn_clear"), callback_data="clear_settings"),
            InlineKeyboardButton(text=await t("settings_btn_close"), callback_data="close_settings")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def get_experience_keyboard(user_id: int):
    """Tajriba darajasi klaviaturasi"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await t("exp_no_experience"), callback_data="exp_no_experience")],
            [InlineKeyboardButton(text=await t("exp_between_1_and_3"), callback_data="exp_between_1_and_3")],
            [InlineKeyboardButton(text=await t("exp_between_3_and_6"), callback_data="exp_between_3_and_6")],
            [InlineKeyboardButton(text=await t("exp_more_than_6"), callback_data="exp_more_than_6")],
            [InlineKeyboardButton(text=await t("exp_not_specified"), callback_data="exp_not_specified")],
            [InlineKeyboardButton(text=await t("btn_back"), callback_data="back_to_settings")]
        ]
    )
    return keyboard


async def get_sources_keyboard(is_premium: bool, user_id: int, current_sources: list = None):
    """Manbalar klaviaturasi"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    current_sources = current_sources or ['hh_uz', 'user_post']
    
    buttons = []
    
    # hh.uz (hammaga)
    hh_selected = '✅' if 'hh_uz' in current_sources else '☐'
    buttons.append([
        InlineKeyboardButton(
            text=f"{hh_selected} {await t('source_hh_uz')}",
            callback_data="toggle_source_hh_uz"
        )
    ])
    
    # User post (hammaga, avtomatik)
    buttons.append([
        InlineKeyboardButton(
            text=f"✅ {await t('source_user_post')} (Auto)",
            callback_data="info_user_post"
        )
    ])
    
    # Telegram (faqat Premium)
    if is_premium:
        tg_selected = '✅' if 'telegram' in current_sources else '☐'
        buttons.append([
            InlineKeyboardButton(
                text=f"{tg_selected} {await t('source_telegram')}",
                callback_data="toggle_source_telegram"
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text=f"🔒 {await t('source_telegram')} (Premium)",
                callback_data="need_premium"
            )
        ])
    
    buttons.extend([
        [InlineKeyboardButton(text=await t("btn_save"), callback_data="save_sources")],
        [InlineKeyboardButton(text=await t("btn_back"), callback_data="back_to_settings")]
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


from utils.i18n import get_msg_options

@router.message(F.text.in_(get_msg_options("menu_settings")))
async def cmd_settings(message: Message):
    """Sozlamalar menyusi"""
    logger.info(f"Settings opened by user {message.from_user.id}")
    
    is_premium = await db.is_premium(message.from_user.id)
    lang = await get_user_lang(message.from_user.id)
    
    text = await get_text("settings_msg_intro", lang=lang)
    
    await message.answer(
        text,
        reply_markup=await get_settings_keyboard(is_premium, message.from_user.id),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "set_language")
async def set_language_menu(callback: CallbackQuery):
    """Tilni o'zgartirish menyusi"""
    await callback.message.edit_text(
        "Iltimos, tilni tanlang:\nПожалуйста, выберите язык:\nPlease select a language:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="settings_lang_uz")],
                [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="settings_lang_ru")],
                [InlineKeyboardButton(text="🇺🇸 English", callback_data="settings_lang_en")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_settings")]
            ]
        )
    )
    await callback.answer()

@router.callback_query(F.data.startswith("settings_lang_"))
async def settings_lang_selected(callback: CallbackQuery):
    """Til tanlandi"""
    lang = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    await db.set_language(user_id, lang)
    
    # Get confirmation text in new language
    text = await get_text("lang_changed", lang=lang)
    
    await callback.answer(text, show_alert=True)
    
    # Go back to settings
    from handlers.start import get_main_keyboard
    
    # Refresh main menu keyboard as well (delete old message or send new one?)
    # Ideally we should refresh the current message to settings menu in new lang
    
    # For now, just back to settings
    await back_to_settings(callback, None) # State might be needed if defined in argument signatures


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, state: FSMContext = None):
    """Sozlamalarga qaytish"""
    if state:
        await state.clear()
    
    user_id = callback.from_user.id
    is_premium = await db.is_premium(user_id)
    lang = await get_user_lang(user_id)
    
    # TODO: Use i18n for this text
    text = await get_text("settings_title", lang=lang) + "\n\n" + await get_text("settings_desc", lang=lang)
    
    await callback.message.edit_text(
        text,
        reply_markup=await get_settings_keyboard(is_premium, user_id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "show_current_settings")
async def show_current_settings(callback: CallbackQuery):
    """Joriy sozlamalarni ko'rsatish"""
    user_filter = await db.get_user_filter(callback.from_user.id)
    
    if not user_filter:
        text = "📊 <b>Joriy sozlamalar</b>\n\n⚠️ Hali sozlamalar o'rnatilmagan."
    else:
        keywords = user_filter.get('keywords', [])
        locations = user_filter.get('locations', [])
        salary_min = user_filter.get('salary_min')
        salary_max = user_filter.get('salary_max')
        experience = user_filter.get('experience_level')
        sources = user_filter.get('sources', ['hh_uz'])
        
        exp_map = {
            'no_experience': '🟢 Tajribasiz',
            'between_1_and_3': '🟡 1-3 yil',
            'between_3_and_6': '🟠 3-6 yil',
            'more_than_6': '🔴 6+ yil',
            'not_specified': '⚪️ Muhim emas'
        }
        
        # Manbalar matni
        sources_text = []
        if 'hh_uz' in sources:
            sources_text.append('🌐 hh.uz')
        if 'user_post' in sources:
            sources_text.append('📢 Bot e\'lonlar')
        if 'telegram' in sources:
            sources_text.append('📱 Telegram')
        
        text = f"""
📊 <b>Joriy sozlamalar</b>

🔑 <b>Kalit so'zlar:</b>
{', '.join(keywords) if keywords else '❌ Belgilanmagan'}

📍 <b>Joylashuv:</b>
{', '.join(locations) if locations else '❌ Barcha joylar'}

💰 <b>Maosh:</b>
{f"dan {salary_min:,} so'm" if salary_min else "❌"} - {f"gacha {salary_max:,} so'm" if salary_max else "cheksiz"}

👔 <b>Tajriba:</b>
{exp_map.get(experience, '⚪️ Muhim emas')}

🌐 <b>Manbalar:</b>
{', '.join(sources_text) if sources_text else '🌐 hh.uz'}
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_settings")]
            ]
        ),
        parse_mode='HTML'
    )
    await callback.answer()


# ========== KALIT SO'ZLAR ==========

@router.callback_query(F.data == "set_keywords")
async def set_keywords_start(callback: CallbackQuery, state: FSMContext):
    """Kalit so'zlarni sozlash"""
    lang = await get_user_lang(callback.from_user.id)
    text = await get_text("prompt_keywords", lang=lang)
    
    await callback.message.edit_text(text, parse_mode='HTML')
    await state.set_state(SettingsStates.waiting_for_keywords)
    await callback.answer()


@router.message(SettingsStates.waiting_for_keywords)
async def process_keywords(message: Message, state: FSMContext):
    """Kalit so'zlarni qayta ishlash"""
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    
    try:
        text = message.text.strip()
        
        if not text:
            await message.answer(await get_text("error_no_keywords", lang=lang))
            return
        
        keywords = [k.strip() for k in text.replace(',', ' ').split() if k.strip()]
        
        user_filter = await db.get_user_filter(user_id) or {}
        user_filter['keywords'] = keywords
        
        success = await db.save_user_filter(user_id, user_filter)
        
        if success:
            success_msg = await get_text("success_keywords", lang=lang)
            next_msg = await get_text("msg_next_steps", lang=lang)
            
            await message.answer(
                f"{success_msg}\n\n"
                f"🔑 {', '.join(keywords)}\n"
                f"{next_msg}",
                reply_markup=await get_settings_keyboard(await db.is_premium(user_id), user_id),
                parse_mode='HTML'
            )
        else:
            await message.answer(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"process_keywords error for user {user_id}: {e}", exc_info=True)
        await message.answer(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        await state.clear()


# ========== JOYLASHUV ==========

@router.callback_query(F.data == "set_locations")
async def set_locations_start(callback: CallbackQuery, state: FSMContext):
    """Joylashuvni sozlash"""
    lang = await get_user_lang(callback.from_user.id)
    text = await get_text("prompt_locations", lang=lang)
    
    await callback.message.edit_text(text, parse_mode='HTML')
    await state.set_state(SettingsStates.waiting_for_locations)
    await callback.answer()


@router.message(SettingsStates.waiting_for_locations)
async def process_locations(message: Message, state: FSMContext):
    """Joylashuvni qayta ishlash"""
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    
    try:
        text = message.text.strip()
        
        if not text:
            await message.answer(await get_text("error_no_locations", lang=lang))
            return
        
        locations = [l.strip().title() for l in text.replace(',', ' ').split() if l.strip()]
        
        user_filter = await db.get_user_filter(user_id) or {}
        user_filter['locations'] = locations
        
        success = await db.save_user_filter(user_id, user_filter)
        
        if success:
            success_msg = await get_text("success_locations", lang=lang)
            next_msg = await get_text("msg_next_steps", lang=lang)
            
            await message.answer(
                f"{success_msg}\n\n"
                f"📍 {', '.join(locations)}\n"
                f"{next_msg}",
                reply_markup=await get_settings_keyboard(await db.is_premium(user_id), user_id),
                parse_mode='HTML'
            )
        else:
            await message.answer(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"process_locations error for user {user_id}: {e}", exc_info=True)
        await message.answer(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        await state.clear()


# ========== MAOSH - FIXED VERSION ==========

@router.callback_query(F.data == "set_salary")
async def set_salary_start(callback: CallbackQuery, state: FSMContext):
    """Maoshni sozlash - FIXED"""
    lang = await get_user_lang(callback.from_user.id)
    text = await get_text("prompt_salary_min", lang=lang)
    
    await callback.message.edit_text(text, parse_mode='HTML')
    await state.set_state(SettingsStates.waiting_for_min_salary)
    await callback.answer()


@router.message(SettingsStates.waiting_for_min_salary)
async def process_min_salary(message: Message, state: FSMContext):
    """Minimal maoshni qayta ishlash - FIXED"""
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    
    try:
        if message.text.strip() == "/skip":
            min_salary = None
            await state.update_data(salary_min=None)
        else:
            try:
                min_salary = int(message.text.strip().replace(' ', '').replace(',', ''))
                if min_salary < 0:
                    await message.answer(await get_text("error_salary_negative", lang=lang))
                    return
                await state.update_data(salary_min=min_salary)
            except ValueError:
                await message.answer(await get_text("error_salary_format", lang=lang))
                return
        
        await message.answer(await get_text("prompt_salary_max", lang=lang), parse_mode='HTML')
        await state.set_state(SettingsStates.waiting_for_max_salary)
        
    except Exception as e:
        logger.error(f"[MIN_SALARY] Error for user {user_id}: {e}", exc_info=True)
        await message.answer(await get_text("msg_error_retry", lang=lang))
        await state.clear()


@router.message(SettingsStates.waiting_for_max_salary)
async def process_max_salary(message: Message, state: FSMContext):
    """Maksimal maoshni qayta ishlash - FIXED"""
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    
    try:
        # State'dan minimal maoshni olish
        data = await state.get_data()
        min_salary = data.get('salary_min')
        
        if message.text.strip() == "/skip":
            max_salary = None
        else:
            try:
                max_salary = int(message.text.strip().replace(' ', '').replace(',', ''))
                if max_salary < 0:
                    await message.answer(await get_text("error_salary_negative", lang=lang))
                    return
                if min_salary and max_salary < min_salary:
                    err_msg = await get_text("error_salary_compare", lang=lang)
                    await message.answer(
                        err_msg.format(max=f"{max_salary:,}", min=f"{min_salary:,}"),
                        parse_mode='HTML'
                    )
                    return
            except ValueError:
                await message.answer(await get_text("error_salary_format", lang=lang))
                return
        
        # Database'ga saqlash
        user_filter = await db.get_user_filter(user_id) or {}
        user_filter['salary_min'] = min_salary
        user_filter['salary_max'] = max_salary
        
        success = await db.save_user_filter(user_id, user_filter)
        
        if success:
            salary_text = ""
            val_from = await get_text("settings_val_from", lang=lang)
            val_to = await get_text("settings_val_to", lang=lang)
            val_unlimited = await get_text("settings_val_unlimited", lang=lang)
            val_not_spec = await get_text("salary_not_specified", lang=lang)

            if min_salary and max_salary:
                salary_text = f"{min_salary:,} - {max_salary:,} so'm"
            elif min_salary:
                salary_text = f"{val_from} {min_salary:,} so'm"
            elif max_salary:
                salary_text = f"{val_to} {max_salary:,} so'm"
            else:
                salary_text = val_not_spec
            
            success_msg = await get_text("success_salary", lang=lang)
            next_msg = await get_text("msg_next_steps", lang=lang)

            await message.answer(
                f"{success_msg}\n\n"
                f"💰 {salary_text}\n"
                f"{next_msg}",
                reply_markup=await get_settings_keyboard(await db.is_premium(user_id), user_id),
                parse_mode='HTML'
            )
        else:
            await message.answer(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"[MAX_SALARY] Error for user {user_id}: {e}", exc_info=True)
        await message.answer(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        await state.clear()


# ========== TAJRIBA ==========

# ========== TAJRIBA ==========

@router.callback_query(F.data == "set_experience")
async def set_experience_start(callback: CallbackQuery):
    """Tajribani sozlash"""
    lang = await get_user_lang(callback.from_user.id)
    text = await get_text("prompt_experience", lang=lang)
    
    await callback.message.edit_text(
        text,
        reply_markup=await get_experience_keyboard(callback.from_user.id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("exp_"))
async def process_experience(callback: CallbackQuery):
    """Tajribani qayta ishlash"""
    user_id = callback.from_user.id
    experience = callback.data.replace("exp_", "")
    lang = await get_user_lang(user_id)
    
    try:
        user_filter = await db.get_user_filter(user_id) or {}
        user_filter['experience_level'] = experience
        
        success = await db.save_user_filter(user_id, user_filter)
        
        # Mapping logic moved to locale files more or less, but we need to display selected one
        # Actually I can use get_text(f"exp_{experience}")
        
        if success:
            exp_text = await get_text(f"exp_{experience}", lang=lang)
            success_msg = await get_text("success_experience", lang=lang)
            next_msg = await get_text("msg_next_steps", lang=lang)

            await callback.message.edit_text(
                f"{success_msg}\n\n"
                f"👔 {exp_text}\n"
                f"{next_msg}",
                reply_markup=await get_settings_keyboard(await db.is_premium(user_id), user_id),
                parse_mode='HTML'
            )
        else:
            await callback.message.edit_text(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"process_experience error for user {user_id}: {e}", exc_info=True)
        await callback.answer(await get_text("msg_error_retry", lang=lang), show_alert=True)


# ========== MANBALAR ==========

@router.callback_query(F.data == "set_sources")
async def set_sources(callback: CallbackQuery, state: FSMContext):
    """Manbalarni sozlash"""
    is_premium = await db.is_premium(callback.from_user.id)
    user_filter = await db.get_user_filter(callback.from_user.id) or {}
    lang = await get_user_lang(callback.from_user.id)
    
    current_sources = user_filter.get('sources', ['hh_uz', 'user_post'])
    
    if 'user_post' not in current_sources:
        current_sources.append('user_post')
    
    await state.update_data(temp_sources=current_sources.copy())
    
    text = await get_text("source_msg_intro", lang=lang)
    
    if not is_premium:
        text += await get_text("source_msg_premium_hint", lang=lang)
    
    await callback.message.edit_text(
        text,
        reply_markup=await get_sources_keyboard(is_premium, callback.from_user.id, current_sources),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_source_"))
async def toggle_source(callback: CallbackQuery, state: FSMContext):
    """Manbani yoqish/o'chirish"""
    source = callback.data.replace("toggle_source_", "")
    
    data = await state.get_data()
    temp_sources = data.get('temp_sources', ['hh_uz', 'user_post'])
    
    if source in temp_sources:
        if len(temp_sources) > 1 and source != 'user_post':
            temp_sources.remove(source)
    else:
        temp_sources.append(source)
    
    await state.update_data(temp_sources=temp_sources)
    
    is_premium = await db.is_premium(callback.from_user.id)
    
    try:
        await callback.message.edit_reply_markup(
            reply_markup=await get_sources_keyboard(is_premium, callback.from_user.id, temp_sources)
        )
    except:
        pass
    
    await callback.answer()


@router.callback_query(F.data == "save_sources")
async def save_sources(callback: CallbackQuery, state: FSMContext):
    """Manbalarni saqlash"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    data = await state.get_data()
    temp_sources = data.get('temp_sources', ['hh_uz', 'user_post'])
    
    if 'user_post' not in temp_sources:
        temp_sources.append('user_post')
    
    try:
        user_filter = await db.get_user_filter(user_id) or {}
        user_filter['sources'] = temp_sources
        
        success = await db.save_user_filter(user_id, user_filter)
        
        if success:
            # Helper for constructing list
            async def t(key): return await get_text(key, lang=lang)
            
            sources_text = []
            if 'hh_uz' in temp_sources: sources_text.append(await t("source_hh_uz"))
            if 'user_post' in temp_sources: sources_text.append(await t("source_user_post"))
            if 'telegram' in temp_sources: sources_text.append(await t("source_telegram"))
            
            success_msg = await t("source_saved")
            
            await callback.message.edit_text(
                f"{success_msg}\n\n"
                f"{', '.join(sources_text)}",
                parse_mode='HTML'
            )
        else:
            await callback.message.edit_text(await get_text("msg_error_retry", lang=lang), parse_mode='HTML')
        
        await state.clear()
        await callback.answer()
        
    except Exception as e:
        logger.error(f"save_sources error for user {user_id}: {e}", exc_info=True)
        await callback.answer(await get_text("msg_error_retry", lang=lang), show_alert=True)
        await state.clear()


@router.callback_query(F.data == "info_user_post")
async def info_user_post(callback: CallbackQuery):
    """User post haqida ma'lumot"""
    lang = await get_user_lang(callback.from_user.id)
    text = await get_text("source_info_user_post", lang=lang)
    await callback.answer(text, show_alert=True)


@router.callback_query(F.data == "need_premium")
async def need_premium(callback: CallbackQuery):
    """Premium kerak xabari"""
    lang = await get_user_lang(callback.from_user.id)
    text = await get_text("source_need_premium", lang=lang)
    await callback.answer(text, show_alert=True)




# ========== TOZALASH ==========

# ========== TOZALASH ==========

@router.callback_query(F.data == "clear_settings")
async def clear_settings(callback: CallbackQuery):
    """Sozlamalarni tozalash"""
    lang = await get_user_lang(callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=await get_text("btn_yes", lang=lang), callback_data="confirm_clear"),
                InlineKeyboardButton(text=await get_text("btn_no", lang=lang), callback_data="back_to_settings")
            ]
        ]
    )
    
    await callback.message.edit_text(
        await get_text("prompt_clear", lang=lang),
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_clear")
async def confirm_clear_settings(callback: CallbackQuery):
    """Tozalashni tasdiqlash"""
    lang = await get_user_lang(callback.from_user.id)
    try:
        await db.delete_user_filter(callback.from_user.id)
        await callback.message.edit_text(await get_text("success_clear", lang=lang), parse_mode='HTML')
        await callback.answer()
    except Exception as e:
        logger.error(f"clear_settings error: {e}")
        await callback.answer(await get_text("msg_error_retry", lang=lang), show_alert=True)


@router.callback_query(F.data == "close_settings")
async def close_settings(callback: CallbackQuery):
    """Yopish"""
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "set_role")
async def set_role_start(callback: CallbackQuery):
    """Rolni tanlash"""
    lang = await get_user_lang(callback.from_user.id)
    text = await get_text("prompt_role", lang=lang)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=await get_text("role_seeker", lang=lang), callback_data="confirm_role_seeker"),
                InlineKeyboardButton(text=await get_text("role_employer", lang=lang), callback_data="confirm_role_employer")
            ],
            [InlineKeyboardButton(text=await get_text("btn_back", lang=lang), callback_data="back_to_settings")]
        ]
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_role_"))
async def confirm_role(callback: CallbackQuery):
    """Rolni tasdiqlash"""
    role = callback.data.replace("confirm_role_", "")
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    try:
        async with db.pool.acquire() as conn:
            await conn.execute("UPDATE users SET role = $1 WHERE user_id = $2", role, user_id)
        
        role_text = await get_text("role_seeker", lang=lang) if role == 'seeker' else await get_text("role_employer", lang=lang)
        
        msg = await get_text("success_role", lang=lang)
        await callback.answer(msg.format(role=role_text), show_alert=True)
        
        # Asosiy menyuni yuborish (start.py dagi kabi)
        from handlers.start import get_main_keyboard
        
        success_setup = await get_text("success_role_setup", lang=lang)
        await callback.message.answer(
            success_setup.format(role=role_text),
            reply_markup=await get_main_keyboard(user_id),
            parse_mode='HTML'
        )
        await callback.message.delete()
        
    except Exception as e:
        logger.error(f"confirm_role error: {e}")
        await callback.answer(await get_text("msg_error_retry", lang=lang))


@router.message(F.text == "/cancel")
async def cancel_action(message: Message, state: FSMContext):
    """Bekor qilish"""
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("msg_canceled", lang=lang))