from aiogram import Router, F
import re
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import db
import logging
from uzjobs_scraper import uz_jobs_scraper
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

router = Router()

# Vakansiyalarni sessiyada saqlash
user_vacancies = {}

# Qidiruv jarayonidagi userlar (bir vaqtda bitta qidiruv)
searching_users = set()

# Qidiruv natijalari keshi (keywords + location + source -> vacancies)
# Format: { 'keyword+location+sources': {'time': timestamp, 'vacancies': [...]} }
search_cache = {}
CACHE_TIMEOUT = 300  # 5 daqiqa

# Telegram scraper instanceni import qilish
telegram_scraper_instance = None

try:
    from config import TELEGRAM_ENABLED
    if TELEGRAM_ENABLED:
        from telegram_scraper import telegram_scraper
        telegram_scraper_instance = telegram_scraper
        logger.info("✅ Telegram scraper import qilindi")
    else:
        logger.info("ℹ️ Telegram scraper o'chirilgan (config)")
except Exception as e:
    logger.warning(f"⚠️ Telegram scraper yuklanmadi: {e}")


from utils.i18n import get_text, get_user_lang

async def get_vacancy_keyboard(user_id: int, current_index: int, total: int, vacancy_id: str = None, is_admin: bool = False, source: str = 'hh_uz') -> InlineKeyboardMarkup:
    """Vakansiya uchun klaviatura"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    buttons = []
    
    # Navigatsiya tugmalari
    nav_buttons = []
    
    if current_index > 0:
        nav_buttons.append(
            InlineKeyboardButton(text=await t("nav_prev"), callback_data=f"vac_prev_{current_index}")
        )
    
    nav_buttons.append(
        InlineKeyboardButton(text=f"📊 {current_index + 1}/{total}", callback_data="vac_count")
    )
    
    if current_index < total - 1:
        nav_buttons.append(
            InlineKeyboardButton(text=await t("nav_next"), callback_data=f"vac_next_{current_index}")
        )
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Qo'shimcha tugmalar
    action_buttons = []
    
    if vacancy_id:
        action_buttons.append(
            InlineKeyboardButton(text=await t("btn_save_vacancy"), callback_data=f"vac_save_{vacancy_id}")
        )
        
        # Interview buttons
        action_buttons.append(
            InlineKeyboardButton(text=await t("btn_interview"), callback_data=f"interview_prep_{vacancy_id}")
        )
        
        # Adminlar uchun o'chirish tugmasi (faqat user_post va telegram uchun)
        if is_admin and source != 'hh_uz':
            action_buttons.append(
                InlineKeyboardButton(text=await t("btn_delete_admin"), callback_data=f"delete_vacancy_{vacancy_id}")
            )
    
    action_buttons.append(
        InlineKeyboardButton(text=await t("btn_new_search"), callback_data="new_search")
    )
    
    buttons.append(action_buttons)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_vacancy_to_user(message_or_callback, user_id: int, index: int):
    """Vakansiyani yuborish yoki yangilash"""
    lang = await get_user_lang(user_id)
    
    if user_id not in user_vacancies:
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(await get_text("session_expired", lang=lang), show_alert=True)
        return
    
    data = user_vacancies[user_id]
    vacancies = data['vacancies']
    
    if index < 0 or index >= len(vacancies):
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(await get_text("vacancy_not_found", lang=lang), show_alert=True)
        return
    
    vacancy = vacancies[index]
    data['current_index'] = index
    
    # Vakansiyani formatlash
    from filters import vacancy_filter
    vacancy_text = vacancy_filter.format_vacancy_message(vacancy, lang=lang)
    
    # To'liq ma'lumot tugmasi
    url_button = InlineKeyboardButton(
        text=await get_text("btn_full_info", lang=lang),
        url=vacancy.get('url', '#')
    )
    
    # Klaviatura yaratish
    vacancy_id = vacancy.get('external_id') or vacancy.get('id')
    
    from config import ADMIN_IDS
    is_admin = user_id in ADMIN_IDS
    vacancy_source = vacancy.get('source', 'hh_uz')
    
    keyboard = await get_vacancy_keyboard(user_id, index, len(vacancies), str(vacancy_id) if vacancy_id else None, is_admin, vacancy_source)
    keyboard.inline_keyboard.insert(0, [url_button])
    
    try:
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(
                vacancy_text,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            await message_or_callback.answer()
        else:
            await message_or_callback.answer(
                vacancy_text,
                reply_markup=keyboard,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Vakansiya yuborishda xatolik: {e}")
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(await get_text("msg_error_generic", lang=lang), show_alert=True)


from utils.i18n import get_msg_options

@router.message(F.text.in_(get_msg_options("menu_vacancies")))
async def search_choice(message: Message):
    """Qidiruv turini tanlash"""
    lang = await get_user_lang(message.from_user.id)
    async def t(key): return await get_text(key, lang=lang)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=await t("btn_search_vacancies"), callback_data="start_search_vacancies"),
            InlineKeyboardButton(text=await t("btn_search_candidates"), callback_data="start_search_candidates")
        ],
        [InlineKeyboardButton(text=await t("btn_cancel_choice"), callback_data="cancel_choice")]
    ])
    await message.answer(await t("search_choice_title"), reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data == "cancel_choice")
async def cancel_choice(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "start_search_candidates")
async def trigger_candidates_search(callback: CallbackQuery):
    from handlers.candidates import show_candidates
    await show_candidates(callback.message, user_id=callback.from_user.id)
    await callback.message.delete()
    await callback.answer()

@router.callback_query(F.data == "start_search_vacancies")
async def trigger_vacancies_search(callback: CallbackQuery):
    await callback.message.delete()
    # Call the original search logic
    await perform_vacancy_search(callback.message, callback.from_user.id)
    await callback.answer()

async def perform_vacancy_search(message: Message, user_id: int):
    """Vakansiya qidirishning asosiy mantiqi"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)

    # Agar user allaqachon qidirayotgan bo'lsa
    if user_id in searching_users:
        await message.answer(await t("search_already_running"), parse_mode='HTML')
        return
    
    from config import PREMIUM_FEATURES
    
    # Premium tekshirish
    is_premium = await db.is_premium(user_id)
    features = PREMIUM_FEATURES['premium' if is_premium else 'free']
    
    # Foydalanuvchi filtrlarini olish
    user_filter = await db.get_user_filter(user_id)
    
    if not user_filter or not user_filter.get('keywords'):
        await message.answer(await t("search_no_settings"), parse_mode='HTML')
        return
    
    # Qidiruv jarayonini belgilash
    searching_users.add(user_id)
    
    # Qidiruv jarayonini boshlash
    keywords = user_filter.get('keywords', [])
    locations = user_filter.get('locations', ['Tashkent'])
    sources = user_filter.get('sources', ['hh_uz', 'user_post'])
    
    wait_msg = await message.answer(
        (await t("search_start")).format(
            keywords=", ".join(keywords),
            location=locations[0] if locations else "Tashkent"
        ), 
        parse_mode='HTML'
    )
    
    # Kesh kalitini yaratish
    import time
    cache_key = f"{'+'.join(sorted(keywords))}_{locations[0] if locations else 'Tashkent'}_{'+'.join(sorted(sources))}"
    
    # Keshtan tekshirish
    if cache_key in search_cache:
        cached_data = search_cache[cache_key]
        if time.time() - cached_data['time'] < CACHE_TIMEOUT:
            logger.info(f"[SEARCH] Cache hit for {cache_key}")
            vacancies = cached_data['vacancies']
            sources_used = cached_data['sources_used']
            
            # Agar keshda ma'lumot bo'lsa, davom ettiramiz (scraping qilmasdan)
            await process_search_results(message, user_id, vacancies, sources_used, wait_msg, features, user_filter)
            searching_users.discard(user_id)
            return

    try:
        # Vakansiyalarni olish
        from scraper_api import scraper_api
        from filters import vacancy_filter
        
        # Premium bo'lsa, Telegram manbasini avtomatik qo'shish (search da ham)
        if is_premium and 'telegram' not in sources:
            sources.append('telegram')
            
        logger.info(f"[SEARCH] User {user_id}: keywords={keywords}, locations={locations}, sources={sources}")
        
        # Sahifalar soni
        pages = features.get('scraping_pages', 2)
        
        # Vakansiyalar ro'yxati
        vacancies = []
        sources_used = []
        
        # PARALLEL SCRAPING - hammasi bir vaqtda
        tasks = []
        
        # 1. Database'dan user-posted vakansiyalar (FAST)
        async def get_user_posted():
            try:
                logger.info("[SEARCH] Fetching user-posted vacancies...")
                async with db.pool.acquire() as conn:
                    db_vacancies = await conn.fetch('''
                        SELECT 
                            vacancy_id as external_id,
                            title,
                            company,
                            description,
                            salary_min,
                            salary_max,
                            location,
                            experience_level,
                            url,
                            source,
                            published_date
                        FROM vacancies
                        WHERE source = 'user_post'
                        AND published_date > NOW() - INTERVAL '30 days'
                        ORDER BY published_date DESC
                        LIMIT 50
                    ''')
                    
                    user_posted = [dict(row) for row in db_vacancies]
                    
                    if user_posted:
                        logger.info(f"[SEARCH] User-posted: {len(user_posted)} ta")
                        return (await t("source_user_post"), '📢', user_posted)
                    return None
            except Exception as e:
                logger.error(f"[SEARCH] User-posted error: {e}")
                return None
        
        tasks.append(get_user_posted())
        
        # 2. hh.uz dan scraping (PARALLEL)
        async def get_hh_uz():
            if 'hh_uz' in sources:
                try:
                    logger.info(f"[SEARCH] hh.uz scraping: pages={pages}")
                    hh_vacancies = await scraper_api.scrape_hh_uz(
                        keywords=keywords,
                        location=locations[0] if locations else 'Tashkent',
                        pages=pages
                    )
                    if hh_vacancies:
                        logger.info(f"[SEARCH] hh.uz: {len(hh_vacancies)} ta")
                        return (await t("source_hh_uz"), '🌐', hh_vacancies)
                    return None
                except Exception as e:
                    logger.error(f"[SEARCH] hh.uz error: {e}")
                    return None
            return None
        
        tasks.append(get_hh_uz())
        
        # 3. Telegram kanallaridan (PARALLEL, Premium only)
        async def get_telegram():
            if 'telegram' in sources and is_premium:
                try:
                    logger.info("[SEARCH] Fetching Telegram vacancies from DB...")
                    async with db.pool.acquire() as conn:
                        # Bazadan Telegram vakansiyalarni olish
                        tg_db_vacancies = await conn.fetch('''
                            SELECT 
                                vacancy_id as external_id,
                                title,
                                company,
                                description,
                                salary_min,
                                salary_max,
                                location,
                                experience_level,
                                url,
                                source,
                                published_date
                            FROM vacancies
                            WHERE source = 'telegram'
                            AND published_date > NOW() - INTERVAL '7 days'
                            ORDER BY published_date DESC
                            LIMIT 300
                        ''')
                        
                        tg_vacancies = [dict(row) for row in tg_db_vacancies]
                        
                        if tg_vacancies:
                            # Telegram kanallarini guruhlashtirish
                            tg_channels = {}
                            for vac in tg_vacancies:
                                external_id = vac.get('external_id', '')
                                # Parsing tg_@channel_id format
                                if external_id.startswith('tg_'):
                                    parts = external_id.split('_')
                                    if len(parts) >= 2:
                                        channel = parts[1]
                                        tg_channels[channel] = tg_channels.get(channel, 0) + 1
                            
                            logger.info(f"[SEARCH] Telegram DB: {len(tg_vacancies)} ta")
                            return (await t("source_telegram"), '📱', tg_vacancies, tg_channels)
                        return None
                except Exception as e:
                    logger.error(f"[SEARCH] Telegram DB error: {e}")
                    return None
            return None
        
        tasks.append(get_telegram())
        
        # 4. UzJobs (NEW)
        async def get_uzjobs():
            try:
                logger.info("[SEARCH] Fetching from UzJobs...")
                res = await uz_jobs_scraper.scrape_uzjobs(keywords)
                if res:
                    return (await t("source_uzjobs"), '🌐', res)
                return None
            except Exception as e:
                logger.error(f"[SEARCH] UzJobs error: {e}")
                return None
        
        tasks.append(get_uzjobs())
        
        # PARALLEL EXECUTION - HAMMASI BIR VAQTDA!
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Natijalarni yig'ish
        for result in results:
            if result and not isinstance(result, Exception):
                if len(result) == 4:  # Telegram (with channels)
                    name, emoji, vacs, channels = result
                    vacancies.extend(vacs)
                    sources_used.append({
                        'name': name,
                        'emoji': emoji,
                        'count': len(vacs),
                        'channels': channels
                    })
                elif len(result) == 3:  # Others
                    name, emoji, vacs = result
                    vacancies.extend(vacs)
                    sources_used.append({
                        'name': name,
                        'emoji': emoji,
                        'count': len(vacs)
                    })
        
        # Keshga saqlash
        search_cache[cache_key] = {
            'time': time.time(),
            'vacancies': vacancies,
            'sources_used': sources_used
        }
        
        await process_search_results(message, user_id, vacancies, sources_used, wait_msg, features, user_filter)

    except Exception as e:
        logger.error(f"[SEARCH] Qidiruvda xatolik: {e}", exc_info=True)
        try:
            await wait_msg.delete()
        except:
            pass
        await message.answer(await t("search_error"), parse_mode='HTML')
    
    finally:
        # Qidiruv tugadi
        searching_users.discard(user_id)

async def process_search_results(message: Message, user_id: int, vacancies: List[Dict], sources_used: List[Dict], wait_msg: Message, features: Dict, user_filter: Dict):
    """Qidiruv natijalarini qayta ishlash va userga yuborish"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    if not vacancies:
        try:
            await wait_msg.delete()
        except:
            pass
        
        await message.answer(await t("search_not_found"), parse_mode='HTML')
        return
    
    # Filtr qo'llash
    from filters import vacancy_filter
    logger.info(f"[SEARCH] Filtrlash: {len(vacancies)} ta vakansiya")
    filtered_vacancies = vacancy_filter.apply_filters(vacancies, user_filter)
    logger.info(f"[SEARCH] Filtrlash natijasi: {len(filtered_vacancies)} ta")
    
    # Natijalar cheklash (free foydalanuvchilar uchun)
    max_results = features.get('max_results', 10)
    limited = False
    
    if len(filtered_vacancies) > max_results:
        filtered_vacancies = filtered_vacancies[:max_results]
        limited = True
    
    try:
        await wait_msg.delete()
    except:
        pass
    
    if not filtered_vacancies:
        await message.answer(await t("search_filtered_out"), parse_mode='HTML')
        return
    
    # Foydalanuvchi uchun vakansiyalarni saqlash
    user_vacancies[user_id] = {
        'vacancies': filtered_vacancies,
        'current_index': 0
    }
    
    # === NATIJALAR XABARI ===
    res_found = await t("results_found")
    result_text = res_found.format(count=len(filtered_vacancies))
    
    # Manbalardagi natijalar
    if sources_used:
        result_text += await t("results_sources")
        for source in sources_used:
            result_text += f"{source['emoji']} <b>{source['name']}:</b> {source['count']} ta\n"
            
            # Telegram kanallari
            if source['emoji'] == '📱' and source.get('channels'):
                channels_list = []
                for channel, count in sorted(source['channels'].items(), key=lambda x: x[1], reverse=True)[:5]:
                    channels_list.append(f"  • {channel}: {count} ta")
                if channels_list:
                    result_text += "\n".join(channels_list) + "\n"
        
        result_text += "\n"
    
    if limited:
        res_limited = await t("results_limited")
        result_text += res_limited.format(count=max_results)
    
    result_text += await t("results_view_action")
    
    await message.answer(result_text, parse_mode='HTML')
    
    # Birinchi vakansiyani yuborish
    await send_vacancy_to_user(message, user_id, 0)

@router.callback_query(F.data.startswith("vac_next_"))
async def next_vacancy(callback: CallbackQuery):
    """Keyingi vakansiya"""
    try:
        current_index = int(callback.data.split("_")[2])
        await send_vacancy_to_user(callback, callback.from_user.id, current_index + 1)
    except Exception as e:
        logger.error(f"next_vacancy xatolik: {e}")
        lang = await get_user_lang(callback.from_user.id)
        await callback.answer(await get_text("msg_error_generic", lang=lang), show_alert=True)


@router.callback_query(F.data.startswith("vac_prev_"))
async def prev_vacancy(callback: CallbackQuery):
    """Oldingi vakansiya"""
    try:
        current_index = int(callback.data.split("_")[2])
        await send_vacancy_to_user(callback, callback.from_user.id, current_index - 1)
    except Exception as e:
        logger.error(f"prev_vacancy xatolik: {e}")
        lang = await get_user_lang(callback.from_user.id)
        await callback.answer(await get_text("msg_error_generic", lang=lang), show_alert=True)


@router.callback_query(F.data == "vac_count")
async def show_count(callback: CallbackQuery):
    """Statistika"""
    lang = await get_user_lang(callback.from_user.id)
    if callback.from_user.id in user_vacancies:
        data = user_vacancies[callback.from_user.id]
        # TODO: localize "Vakansiya X / Y" if strictly needed, but numbers are fine. 
        # Actually better to have a format string.
        # "status_vacancy_count": "📊 Vakansiya {current} / {total}"
        # I'll stick to simple format for now or add key.
        # Let's add key implicitly or just format string.
        # "Vaccancy" word is the only thing.
        # I'll leave as is for now or use "results_found" style?
        # Let's use hardcoded emoji for now to save time, or better:
        await callback.answer(
            f"📊 {data['current_index'] + 1} / {len(data['vacancies'])}",
            show_alert=False
        )
    else:
        await callback.answer(await get_text("session_expired", lang=lang), show_alert=True)


@router.callback_query(F.data.startswith("vac_save_"))
async def save_vacancy(callback: CallbackQuery):
    """Vakansiyani saqlash"""
    lang = await get_user_lang(callback.from_user.id)
    try:
        vacancy_id = callback.data.split("_", 2)[2]
        await db.add_sent_vacancy(callback.from_user.id, vacancy_id, "Saqlangan")
        await callback.answer(await get_text("vacancy_saved", lang=lang), show_alert=True)
    except Exception as e:
        logger.error(f"Vakansiya saqlashda xatolik: {e}")
        await callback.answer(await get_text("msg_error_generic", lang=lang), show_alert=True)


@router.callback_query(F.data == "new_search")
async def new_search(callback: CallbackQuery):
    """Yangi qidiruv"""
    lang = await get_user_lang(callback.from_user.id)
    if callback.from_user.id in user_vacancies:
        del user_vacancies[callback.from_user.id]
    
    await callback.message.answer(
        await get_text("msg_new_search_hint", lang=lang),
        parse_mode='HTML'
    )
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.answer()

@router.message(F.text.regexp(r'^/view_(.+)$'))
async def view_vacancy_handler(message: Message):
    """Vakansiyani ID orqali ko'rish"""
    lang = await get_user_lang(message.from_user.id)
    try:
        from filters import vacancy_filter
        # Regex orqali ID ni olish
        match = re.match(r'^/view_(.+)$', message.text)
        if not match:
            return
            
        vacancy_id = match.group(1)
        vac = await db.get_vacancy(vacancy_id)
        
        if not vac:
            await message.answer(await get_text("vacancy_not_found", lang=lang))
            return
            
        text = vacancy_filter.format_vacancy_message(vac, lang=lang)
        
        from handlers.favorites import get_favorite_keyboard
        await message.answer(
            text,
            reply_markup=await get_favorite_keyboard(message.from_user.id, vacancy_id),
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"view_vacancy_handler error: {e}")
        await message.answer(await get_text("msg_error_generic", lang=lang))
