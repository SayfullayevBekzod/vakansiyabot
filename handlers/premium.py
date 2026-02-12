from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from config import PREMIUM_FEATURES, PREMIUM_PRICE, ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

router = Router()


# FSM States
class PremiumStates(StatesGroup):
    waiting_for_payment_proof = State()
    waiting_for_plan_selection = State()


from utils.i18n import get_text, get_user_lang

async def get_premium_keyboard(user_id: int):
    """Premium klaviatura"""
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=await t("premium_btn_buy"),
                    callback_data="buy_premium"
                )
            ],
            [
                InlineKeyboardButton(
                    text=await t("premium_btn_plans"),
                    callback_data="premium_plans"
                )
            ],
            [
                InlineKeyboardButton(
                    text=await t("btn_back"),
                    callback_data="close_premium"
                )
            ]
        ]
    )
    return keyboard


async def get_plans_keyboard(user_id: int):
    """Tariflar klaviaturasi"""
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=await t("plan_monthly", price=f"{PREMIUM_PRICE['monthly']:,}"),
                    callback_data="plan_monthly"
                )
            ],
            [
                InlineKeyboardButton(
                    text=await t("plan_yearly", price=f"{PREMIUM_PRICE['yearly']:,}"),
                    callback_data="plan_yearly"
                )
            ],
            [
                InlineKeyboardButton(
                    text=await t("btn_back"),
                    callback_data="show_premium"
                )
            ]
        ]
    )
    return keyboard


def get_payment_confirm_keyboard(user_id: int, days: int):
    """Admin uchun tasdiqlash klaviaturasi"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"approve_payment_{user_id}_{days}"
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=f"reject_payment_{user_id}_{days}"
                )
            ]
        ]
    )
    return keyboard


from utils.i18n import get_msg_options

@router.message(F.text.in_(get_msg_options("menu_premium")))
async def cmd_premium(message: Message):
    """Premium bo'limi"""
    user_id = message.from_user.id
    is_premium = await db.is_premium(user_id)
    user = await db.get_user(user_id)
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    if is_premium:
        premium_until = user.get('premium_until')
        if premium_until:
            date_str = premium_until.strftime('%d.%m.%Y')
            time_str = premium_until.strftime('%H:%M')
            
            # Qancha kun qolganini hisoblash
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if premium_until.tzinfo is None:
                premium_until = premium_until.replace(tzinfo=timezone.utc)
            
            days_left = (premium_until - now).days
            
            if days_left < 0:
                days_text = await t("premium_status_expired")
            elif days_left == 0:
                days_text = await t("premium_status_today")
            else:
                days_text = await t("premium_status_days", days=days_left)
        else:
            date_str = await t("premium_status_infinite")
            time_str = ""
            days_text = await t("premium_status_infinite")
        
        # Klaviatura - faqat uzaytirish
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=await t("premium_btn_extend"),
                        callback_data="extend_premium"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await t("premium_btn_plans"),
                        callback_data="premium_plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await t("premium_btn_support"),
                        url="https://t.me/SayfullayevBekzod"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await t("btn_back"),
                        callback_data="close_premium"
                    )
                ]
            ]
        )
        
        text = await t("premium_user_desc", date=date_str, time=time_str, status=days_text) + "\n\n"
        text += await t("premium_extend_hint")
        
        await message.answer(await t("premium_user_title") + "\n\n" + text, reply_markup=keyboard, parse_mode='HTML')
        return
    
    # FREE foydalanuvchi uchun
    else:
        free_features = PREMIUM_FEATURES['free']
        
        text = await t("premium_intro_title") + "\n\n"
        text += await t("premium_free_ver", searches=free_features['max_searches_per_day'], results=free_features['max_results']) + "\n\n"
        text += await t("premium_full_ver") + "\n\n"
        text += await t("premium_prices", monthly=f"{PREMIUM_PRICE['monthly']:,}", yearly=f"{PREMIUM_PRICE['yearly']:,}")
    
    await message.answer(
        text,
        reply_markup=await get_premium_keyboard(user_id),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "show_premium")
async def show_premium(callback: CallbackQuery):
    """Premium ma'lumotini ko'rsatish"""
    user_id = callback.from_user.id
    is_premium = await db.is_premium(user_id)
    user = await db.get_user(user_id)
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    if is_premium:
        premium_until = user.get('premium_until')
        if premium_until:
            date_str = premium_until.strftime('%d.%m.%Y')
            time_str = premium_until.strftime('%H:%M')
            
            # Qancha kun qolganini hisoblash
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if premium_until.tzinfo is None:
                premium_until = premium_until.replace(tzinfo=timezone.utc)
            
            days_left = (premium_until - now).days
            
            if days_left < 0:
                days_text = await t("premium_status_expired")
            elif days_left == 0:
                days_text = await t("premium_status_today")
            else:
                days_text = await t("premium_status_days", days=days_left)
        else:
            date_str = await t("premium_status_infinite")
            time_str = ""
            days_text = await t("premium_status_infinite")
        
        # Klaviatura
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=await t("premium_btn_extend"),
                        callback_data="extend_premium"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await t("premium_btn_plans"),
                        callback_data="premium_plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await t("premium_btn_support"),
                        url="https://t.me/SayfullayevBekzod"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await t("btn_back"),
                        callback_data="close_premium"
                    )
                ]
            ]
        )
        
        text = await t("premium_user_desc", date=date_str, time=time_str, status=days_text)
        
        await callback.message.edit_text(await t("premium_user_title") + "\n\n" + text, reply_markup=keyboard, parse_mode='HTML')
        await callback.answer()
        return
    
    # FREE foydalanuvchi uchun
    else:
        free_features = PREMIUM_FEATURES['free']
        
        text = await t("premium_intro_title") + "\n\n"
        text += await t("premium_free_ver", searches=free_features['max_searches_per_day'], results=free_features['max_results']) + "\n\n"
        text += await t("premium_full_ver")
    
    await callback.message.edit_text(
        text,
        reply_markup=await get_premium_keyboard(user_id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "extend_premium")
async def extend_premium(callback: CallbackQuery):
    """Premium'ni uzaytirish"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)

    await callback.message.edit_text(
        await t("premium_extend_title"),
        reply_markup=await get_plans_keyboard(user_id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    """Premium sotib olish - avval tekshirish"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    is_premium = await db.is_premium(user_id)
    
    if is_premium:
        # Agar allaqachon Premium bo'lsa
        await callback.answer(
            await t("premium_aleady_active"),
            show_alert=True
        )
        return
    
    # FREE foydalanuvchi uchun - tariflar
    await callback.message.edit_text(
        await t("premium_plans_title"),
        reply_markup=await get_plans_keyboard(user_id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data == "premium_plans")
async def show_plans(callback: CallbackQuery):
    """Tariflarni ko'rsatish"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    await callback.message.edit_text(
        await t("premium_prices", monthly=f"{PREMIUM_PRICE['monthly']:,}", yearly=f"{PREMIUM_PRICE['yearly']:,}") + "\n\n" + await t("premium_full_ver"),
        reply_markup=await get_plans_keyboard(user_id),
        parse_mode='HTML'
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan_"))
async def select_plan(callback: CallbackQuery, state: FSMContext):
    """Tarif tanlash"""
    # Premium tekshirish
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    is_premium = await db.is_premium(user_id)
    user = await db.get_user(user_id)
    
    plan = callback.data.replace("plan_", "")
    
    if plan == "monthly":
        price = PREMIUM_PRICE['monthly']
        period = await t("period_1_month")
        days = 30
    else:
        price = PREMIUM_PRICE['yearly']
        period = await t("period_1_year")
        days = 365
    
    # State'ga saqlash
    await state.update_data(
        plan=plan, 
        days=days, 
        price=price, 
        period=period,
        is_extension=is_premium
    )
    
    # Xabar matni
    if is_premium:
        premium_until = user.get('premium_until')
        if premium_until:
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            if premium_until.tzinfo is None:
                premium_until = premium_until.replace(tzinfo=timezone.utc)
            
            # Yangi tugash sanasi
            new_expiry = premium_until + timedelta(days=days)
            new_date_str = new_expiry.strftime('%d.%m.%Y')
            
            action_text = await t("action_extend")
            extra_info = f"\n\n📅 {new_date_str}" # Simplified as key requires complexity
        else:
            action_text = await t("action_extend")
            extra_info = ""
    else:
        action_text = await t("action_activate")
        from datetime import datetime, timezone, timedelta
        new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
        new_date_str = new_expiry.strftime('%d.%m.%Y')
        extra_info = f"\n\n📅 {new_date_str}"
    
    await callback.message.edit_text(
        await t("premium_plan_selected", period=period, price=f"{price:,}", days=days, extra=extra_info, action=action_text),
        parse_mode='HTML'
    )
    
    await state.set_state(PremiumStates.waiting_for_payment_proof)
    await callback.answer()


@router.message(PremiumStates.waiting_for_payment_proof, F.photo)
async def process_payment_proof(message: Message, state: FSMContext):
    """To'lov chekini qabul qilish"""
    data = await state.get_data()
    plan = data.get('plan')
    days = data.get('days')
    price = data.get('price')
    period = data.get('period')
    is_extension = data.get('is_extension', False)
    
    user = message.from_user
    photo = message.photo[-1]  # Eng katta o'lchamdagi rasm
    lang = await get_user_lang(user.id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    # Foydalanuvchiga javob
    action_text = await t("action_extend") if is_extension else await t("action_activate")
    
    await message.answer(
        await t("premium_payment_received", action=action_text),
        parse_mode='HTML'
    )
    
    # Premium status tekshirish
    is_premium = await db.is_premium(user.id)
    user_data = await db.get_user(user.id)
    
    if is_premium:
        premium_until = user_data.get('premium_until')
        if premium_until:
            from datetime import timedelta
            if premium_until.tzinfo is None:
                from datetime import timezone
                premium_until = premium_until.replace(tzinfo=timezone.utc)
            
            new_expiry = premium_until + timedelta(days=days)
            current_status = f"📅 Hozirgi tugash: {premium_until.strftime('%d.%m.%Y')}\n📅 Yangi tugash: {new_expiry.strftime('%d.%m.%Y')}"
            action_emoji = "🔄"
            action_word = "UZAYTIRISH"
        else:
            current_status = "📅 Premium: Abadiy"
            action_emoji = "🔄"
            action_word = "UZAYTIRISH"
    else:
        from datetime import datetime, timezone, timedelta
        new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
        current_status = f"📅 Premium beriladi: {new_expiry.strftime('%d.%m.%Y')} gacha"
        action_emoji = "💎"
        action_word = "YANGI OBUNA"
    
    # Adminlarga yuborish
    for admin_id in ADMIN_IDS:
        try:
            # Rasmni yuborish
            caption = f"""
💳 <b>{action_emoji} {action_word} - TO'LOV CHEKI</b>

👤 <b>Foydalanuvchi:</b>
• Ism: {user.first_name} {user.last_name or ''}
• Username: @{user.username or 'N/A'}
• ID: <code>{user.id}</code>

💎 <b>Tarif:</b>
• Reja: {period}
• Narx: {price:,} so'm
• Davomiyligi: {days} kun

📊 <b>Holat:</b>
• Status: {'Premium (uzaytirish)' if is_extension else 'FREE (yangi)'}
{current_status}

📅 <b>Vaqt:</b> {message.date.strftime('%d.%m.%Y %H:%M')}

⬇️ <b>Chekni tekshiring va harakatni tanlang:</b>
"""
            
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=caption,
                reply_markup=get_payment_confirm_keyboard(user.id, days),
                parse_mode='HTML'
            )
            
            logger.info(f"✅ Chek admin {admin_id} ga yuborildi (Extension: {is_extension})")
            
        except Exception as e:
            logger.error(f"❌ Admin {admin_id} ga chek yuborishda xatolik: {e}")
    
    await state.clear()


@router.message(PremiumStates.waiting_for_payment_proof)
async def payment_proof_invalid(message: Message):
    """Noto'g'ri format (rasm emas)"""
    lang = await get_user_lang(message.from_user.id)
    await message.answer(
        await get_text("premium_payment_invalid", lang=lang),
        parse_mode='HTML'
    )


@router.callback_query(F.data.startswith("approve_payment_"))
async def approve_payment(callback: CallbackQuery):
    """Admin: To'lovni tasdiqlash"""
    try:
        parts = callback.data.split("_")
        user_id = int(parts[2])
        days = int(parts[3])
        
        # Hozirgi premium statusni tekshirish
        is_premium = await db.is_premium(user_id)
        user = await db.get_user(user_id)
        
        if is_premium:
            premium_until = user.get('premium_until')
            if premium_until:
                from datetime import timezone, timedelta
                if premium_until.tzinfo is None:
                    premium_until = premium_until.replace(tzinfo=timezone.utc)
                
                old_date = premium_until.strftime('%d.%m.%Y')
                
                # Uzaytirish
                new_expiry = premium_until + timedelta(days=days)
                
                action_text = "uzaytirildi"
                status_text = f"📅 Eski: {old_date}\n📅 Yangi: {new_expiry.strftime('%d.%m.%Y')}"
            else:
                old_date = "Abadiy"
                action_text = "uzaytirildi"
                status_text = "Premium uzaytirildi"
        else:
            action_text = "berildi"
            from datetime import datetime, timezone, timedelta
            new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
            status_text = f"📅 Tugash: {new_expiry.strftime('%d.%m.%Y')}"
        
        # Premium berish/uzaytirish
        success = await db.set_premium(user_id, days)
        
        if success:
            # Adminга javob
            await callback.message.edit_caption(
                caption=callback.message.caption + f"\n\n✅ <b>TASDIQLANDI!</b>\n"
                f"💎 Premium {days} kunga {action_text}.\n{status_text}",
                parse_mode='HTML'
            )
            
            # Foydalanuvchiga xabar
            try:
                lang = await get_user_lang(user_id)
                user = await db.get_user(user_id)
                premium_until = user.get('premium_until')
                date_str = premium_until.strftime('%d.%m.%Y') if premium_until else 'Abadiy'
                
                # Localized action text
                action_key = "action_extended" if is_premium else "action_activated"
                action_localized = await get_text(action_key, lang=lang)
                
                await callback.bot.send_message(
                    user_id,
                    await get_text("premium_payment_approved", lang=lang, action=action_localized, date=date_str),
                    parse_mode='HTML'
                )
                
                logger.info(f"✅ User {user_id} premium {action_text}: {days} kun")
                
            except Exception as e:
                logger.error(f"❌ User {user_id} ga xabar yuborishda xatolik: {e}")
            
            await callback.answer("✅ Premium berildi!", show_alert=True)
        else:
            await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
            
    except Exception as e:
        logger.error(f"❌ approve_payment xatolik: {e}", exc_info=True)
        await callback.answer("❌ Xatolik!", show_alert=True)


@router.callback_query(F.data.startswith("reject_payment_"))
async def reject_payment(callback: CallbackQuery):
    """Admin: To'lovni bekor qilish"""
    try:
        parts = callback.data.split("_")
        user_id = int(parts[2])
        days = int(parts[3])
        
        # Adminга javob
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n❌ <b>BEKOR QILINDI!</b>",
            parse_mode='HTML'
        )
        
        # Foydalanuvchiga xabar
        try:
            lang = await get_user_lang(user_id)
            await callback.bot.send_message(
                user_id,
                await get_text("premium_payment_rejected", lang=lang),
                parse_mode='HTML'
            )
            
            logger.info(f"❌ User {user_id} to'lovi rad etildi")
            
        except Exception as e:
            logger.error(f"❌ User {user_id} ga xabar yuborishda xatolik: {e}")
        
        await callback.answer("❌ To'lov rad etildi", show_alert=True)
        
    except Exception as e:
        logger.error(f"❌ reject_payment xatolik: {e}", exc_info=True)
        await callback.answer("❌ Xatolik!", show_alert=True)


@router.callback_query(F.data == "close_premium")
async def close_premium(callback: CallbackQuery):
    """Premium oynasini yopish"""
    await callback.message.delete()
    await callback.answer()


@router.message(F.text == "/cancel")
async def cancel_payment(message: Message, state: FSMContext):
    """To'lovni bekor qilish"""
    current_state = await state.get_state()
    
    if current_state == PremiumStates.waiting_for_payment_proof:
        await state.clear()
        lang = await get_user_lang(message.from_user.id)
        await message.answer(
            await get_text("premium_cancel", lang=lang),
            parse_mode='HTML'
        )
    else:
        await message.answer("...") # Slient fail or usage info