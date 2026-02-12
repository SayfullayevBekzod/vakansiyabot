from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from utils.i18n import get_text, get_user_lang
import logging

logger = logging.getLogger(__name__)

router = Router()

async def get_main_keyboard(user_id: int):
    """Asosiy klaviatura - Premium va funksiyalarga qarab"""
    is_premium = await db.is_premium(user_id)
    lang = await get_user_lang(user_id)
    
    # helper for concise text getting
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    keyboard_buttons = [
        [
            KeyboardButton(text=await t("menu_vacancies")),
            KeyboardButton(text=await t("menu_settings"))
        ],
        [
            KeyboardButton(text=await t("menu_premium")),
            KeyboardButton(text=await t("menu_saved"))
        ]
    ]
    
    # Premium foydalanuvchilar uchun qo'shimcha funksiyalar
    if is_premium:
        keyboard_buttons.insert(2, [
            KeyboardButton(text=await t("menu_add_vacancy")),
            KeyboardButton(text=await t("menu_smart"))
        ])
        keyboard_buttons.insert(3, [
            KeyboardButton(text=await t("menu_notifications")),
            KeyboardButton(text=await t("menu_stats"))
        ])
    else:
        keyboard_buttons.insert(2, [
            KeyboardButton(text=await t("menu_stats"))
        ])
    
    # Referral va Yordam barcha uchun
    keyboard_buttons.append([
        KeyboardButton(text=await t("menu_referral")),
        KeyboardButton(text=await t("menu_help"))
    ])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True
    )
    return keyboard


# FSM States
class StartStates(StatesGroup):
    waiting_for_language = State()
    waiting_for_role = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Start komandasi"""
    user = message.from_user
    
    # Foydalanuvchini bazaga qo'shish
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Referral checking
    if message.text and len(message.text.split()) > 1:
        args = message.text.split()[1]
        if args.startswith('ref_'):
            try:
                referrer_id = int(args.replace('ref_', ''))
                from handlers.referral import process_referral_start
                await process_referral_start(message, referrer_id)
            except:
                pass

    # Force Language Selection for better UX
    await message.answer(
        "Iltimos, tilni tanlang:\nПожалуйста, выберите язык:\nPlease select a language:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz")],
                [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
                [InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")]
            ]
        )
    )
    await state.set_state(StartStates.waiting_for_language)

@router.callback_query(StartStates.waiting_for_language, F.data.startswith("lang_"))
async def language_selected(callback: CallbackQuery, state: FSMContext):
    """Language selection handler"""
    lang_code = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    await db.set_language(user_id, lang_code)
    
    # Get localized welcome message
    welcome_text = await get_text("welcome_intro", lang=lang_code)
    # Append name
    welcome_text += f"\n\n{callback.from_user.first_name}"
    
    role_text = await get_text("select_role_title", lang=lang_code)
    
    await callback.message.edit_text(
        welcome_text,
        parse_mode='HTML'
    )
    
    # Ask for Role
    await callback.message.answer(
        role_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=await get_text("role_seeker", lang=lang_code), callback_data="role_seeker")],
                [InlineKeyboardButton(text=await get_text("role_employer", lang=lang_code), callback_data="role_employer")]
            ]
        )
    )
    await state.set_state(StartStates.waiting_for_role)
    await callback.answer()

@router.callback_query(StartStates.waiting_for_role, F.data.startswith("role_"))
async def role_selected(callback: CallbackQuery, state: FSMContext):
    """Role selection handler"""
    role = callback.data.replace("role_", "")
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    # Update role in DB
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET role = $1 WHERE user_id = $2", role, user_id)
    
    await callback.message.delete()
    
    # Send main menu
    await send_main_menu(callback.message, user_id)
    await state.clear()
    await callback.answer()

async def send_main_menu(message: Message, user_id: int, prefix_text: str = ""):
    """Asosiy menyuni yuborish"""
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    # Get Updated Role
    role = await db.pool.fetchval("SELECT role FROM users WHERE user_id = $1", user_id)
    
    # Premium label
    is_premium = await db.is_premium(user_id)
    premium_label = " 💎" if is_premium else ""
    user = await db.get_user(user_id)
    name = user.get('first_name', 'Foydalanuvchi')
    
    welcome_text = prefix_text + await t("welcome_intro", name=name, premium_label=premium_label) + "\n\n"
    
    if role == 'employer':
        welcome_text += await t("welcome_employer") + "\n"
    else:
        welcome_text += await t("welcome_seeker") + "\n"
        
    welcome_text += "\n" + await t("welcome_footer")

    await message.answer(
        welcome_text,
        reply_markup=await get_main_keyboard(user_id),
        parse_mode='HTML'
    )


from utils.i18n import get_msg_options

@router.message(F.text.in_(get_msg_options("menu_help")))
@router.message(Command("help"))
async def cmd_help(message: Message):
    """Yordam komandasi"""
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    
    help_text = await get_text("help_text_main", lang=lang)
    
    await message.answer(help_text, parse_mode='HTML')


@router.message(F.text.in_(get_msg_options("menu_stats")))
async def cmd_stats(message: Message):
    """Statistika"""
    # Analytics handler'ga yo'naltirish
    from handlers.analytics import cmd_analytics
    await cmd_analytics(message)
