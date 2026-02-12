
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = Router()

# FSM States for Vacancy (Employer)
class PostVacancyStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_company = State()
    waiting_for_description = State()
    waiting_for_salary_min = State()
    waiting_for_salary_max = State()
    waiting_for_location = State()
    waiting_for_experience = State()
    waiting_for_contact = State()
    confirming = State()

# FSM States for Resume (Seeker)
class PostResumeStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_age = State()
    waiting_for_technology = State()
    waiting_for_telegram = State()
    waiting_for_phone = State()
    waiting_for_region = State()
    waiting_for_salary = State()
    waiting_for_profession = State()
    waiting_for_call_time = State()
    waiting_for_goal = State()
    confirming = State()

from utils.i18n import get_text, get_user_lang, get_msg_options

async def get_experience_keyboard(user_id: int):
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await t("btn_no_experience"), callback_data="post_exp_no_experience")],
        [InlineKeyboardButton(text=await t("btn_exp_1_3"), callback_data="post_exp_between_1_and_3")],
        [InlineKeyboardButton(text=await t("btn_exp_3_6"), callback_data="post_exp_between_3_and_6")],
        [InlineKeyboardButton(text=await t("btn_exp_6_plus"), callback_data="post_exp_more_than_6")],
        [InlineKeyboardButton(text=await t("btn_cancel"), callback_data="cancel_post")]
    ])

async def get_confirm_keyboard(prefix, user_id: int):
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=await t("btn_publish"), callback_data=f"confirm_{prefix}"),
            InlineKeyboardButton(text=await t("btn_edit"), callback_data=f"edit_{prefix}")
        ],
        [InlineKeyboardButton(text=await t("btn_cancel"), callback_data="cancel_post")]
    ])

async def get_region_keyboard(user_id: int):
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    regions = ["Toshkent", "Andijon", "Buxoro", "Farg'ona", "Jizzax", "Xorazm", "Namangan", "Navoiy", "Qashqadaryo", "Samarqand", "Sirdaryo", "Surxondaryo", "Qoraqalpog'iston"]
    rows = []
    current_row = []
    for reg in regions:
        current_row.append(InlineKeyboardButton(text=reg, callback_data=f"region_{reg}"))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton(text=await t("btn_cancel"), callback_data="cancel_post")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# --- Entry Points ---

@router.message(F.text.in_(get_msg_options("menu_post_vacancy")))
async def start_add_content(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await t("btn_employer"), callback_data="start_employer_flow")],
        [InlineKeyboardButton(text=await t("btn_seeker"), callback_data="start_seeker_flow")],
        [InlineKeyboardButton(text=await t("btn_cancel"), callback_data="cancel_post")]
    ])
    await message.answer(await t("post_choose_role_title"), reply_markup=keyboard, parse_mode='HTML')

@router.callback_query(F.data == "cancel_post")
async def cancel_post(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(callback.from_user.id)
    await callback.message.edit_text(await get_text("post_cancelled", lang=lang))
    await callback.answer()

@router.message(F.text == "/cancel")
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_cancelled", lang=lang))

# --- EMPLOYER FLOW ---

@router.callback_query(F.data == "start_employer_flow")
async def start_employer_flow(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)

    await db.pool.execute("UPDATE users SET role = 'employer' WHERE user_id = $1", user_id)
    
    is_premium = await db.is_premium(user_id)
    if not is_premium:
        await callback.message.edit_text(
            await t("error_premium_required"),
            parse_mode='HTML'
        )
        return

    await callback.message.edit_text(
        await t("post_employer_step_1"),
        parse_mode='HTML'
    )
    await state.set_state(PostVacancyStates.waiting_for_company)

@router.message(PostVacancyStates.waiting_for_company)
async def process_company(message: Message, state: FSMContext):
    await state.update_data(company=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_employer_step_2", lang=lang))
    await state.set_state(PostVacancyStates.waiting_for_title)

@router.message(PostVacancyStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_employer_step_3", lang=lang))
    await state.set_state(PostVacancyStates.waiting_for_salary_min)

@router.message(PostVacancyStates.waiting_for_salary_min)
async def process_salary_min(message: Message, state: FSMContext):
    await state.update_data(salary_min=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_employer_step_3_max", lang=lang))
    await state.set_state(PostVacancyStates.waiting_for_salary_max)

@router.message(PostVacancyStates.waiting_for_salary_max)
async def process_salary_max(message: Message, state: FSMContext):
    if message.text != "/skip":
        await state.update_data(salary_max=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_employer_step_4", lang=lang))
    await state.set_state(PostVacancyStates.waiting_for_location)

@router.message(PostVacancyStates.waiting_for_location)
async def process_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_employer_step_5", lang=lang), reply_markup=await get_experience_keyboard(message.from_user.id))
    await state.set_state(PostVacancyStates.waiting_for_experience)

@router.callback_query(PostVacancyStates.waiting_for_experience)
async def process_experience(callback: CallbackQuery, state: FSMContext):
    exp = callback.data.replace("post_exp_", "")
    await state.update_data(experience=exp)
    
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    await callback.message.edit_text(await get_text("post_employer_step_6", lang=lang))
    await state.set_state(PostVacancyStates.waiting_for_contact)

@router.message(PostVacancyStates.waiting_for_contact)
async def process_contact(message: Message, state: FSMContext):
    await state.update_data(contact=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_employer_step_7", lang=lang))
    await state.set_state(PostVacancyStates.waiting_for_description)

@router.message(PostVacancyStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    data = await state.get_data()
    
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    preview_template = await t("post_vacancy_preview")
    preview = preview_template.format(
        company=data.get('company'),
        title=data.get('title'),
        salary_min=data.get('salary_min'),
        salary_max=data.get('salary_max', ''),
        location=data.get('location'),
        contact=data.get('contact'),
        description=data.get('description')
    )
    
    await message.answer(preview, reply_markup=await get_confirm_keyboard("vacancy", user_id), parse_mode='HTML')
    await state.set_state(PostVacancyStates.confirming)

@router.callback_query(F.data == "confirm_vacancy")
async def confirm_vacancy(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    now = datetime.now(timezone.utc)
    vacancy_id = f"user_{callback.from_user.id}_{int(now.timestamp())}"
    
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)

    try:
        await db.add_vacancy(
            external_id=vacancy_id,
            title=data['title'],
            company=data['company'],
            description=f"{data['description']}\n\n📞 {data['contact']}",
            salary_min=int(data['salary_min']) if data['salary_min'].isdigit() else 0,
            location=data['location'],
            experience_level=data.get('experience', 'N/A'),
            url=f"https://t.me/{callback.from_user.username}",
            source='user_post',
            published_date=now
        )
        await callback.message.edit_text(await t("post_vacancy_success"))
        
        # --- MATCH ALERT - Ish qidiruvchilarga xabar berish ---
        try:
            from filters import vacancy_filter
            seekers = await db.get_all_seekers_with_filters()
            
            # Yangi vakansiya obyekti filtrlash uchun
            new_vacancy = {
                'title': data['title'],
                'company': data['company'],
                'description': data['description'],
                'salary_min': int(data['salary_min']) if data['salary_min'].isdigit() else 0,
                'salary_max': int(data['salary_max']) if data.get('salary_max', '').isdigit() else None,
                'location': data['location'],
                'experience_level': data.get('experience', 'N/A'),
                'source': 'user_post',
                'url': f"https://t.me/{callback.from_user.username or 'bot'}",
                'published_date': now
            }
            
            count = 0
            for seeker in seekers:
                # Seeker filtrlarini tayyorlash
                seeker_filter = {
                    'keywords': seeker.get('keywords', []),
                    'locations': seeker.get('locations', []),
                    'min_salary': seeker.get('salary_min'),
                    'max_salary': seeker.get('salary_max'),
                    'experience_level': seeker.get('experience_level')
                }
                
                # Mos kelishini tekshirish
                if vacancy_filter.apply_filters([new_vacancy], seeker_filter):
                    try:
                        seeker_lang = await get_user_lang(seeker['user_id'])
                        alert_title = await get_text("post_match_alert", lang=seeker_lang)
                        alert_text = f"{alert_title}{vacancy_filter.format_vacancy_message(new_vacancy, lang=seeker_lang)}"
                        
                        await callback.bot.send_message(
                            seeker['user_id'],
                            alert_text,
                            parse_mode='HTML',
                            disable_web_page_preview=True
                        )
                        count += 1
                    except Exception as e:
                        logger.error(f"Alert yuborishda xatolik (user {seeker['user_id']}): {e}")
            
            logger.info(f"Match Alert: {count} ta foydalanuvchiga xabar yuborildi.")
        except Exception as e:
            logger.error(f"Match Alert jarayonida xatolik: {e}")

    except Exception as e:
        logger.error(f"Error posting vacancy: {e}")
        await callback.message.edit_text(await t("error_generic"))
    await state.clear()

# --- SEEKER FLOW (RESUME) ---

@router.callback_query(F.data == "start_seeker_flow")
async def start_seeker_flow(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    await db.pool.execute("UPDATE users SET role = 'seeker' WHERE user_id = $1", user_id)
    await callback.message.edit_text(await t("post_resume_step_1"), parse_mode='HTML')
    await state.set_state(PostResumeStates.waiting_for_name)

@router.message(PostResumeStates.waiting_for_name)
async def resume_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_resume_step_2", lang=lang))
    await state.set_state(PostResumeStates.waiting_for_age)

@router.message(PostResumeStates.waiting_for_age)
async def resume_age(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    
    if not message.text.isdigit():
        await message.answer(await get_text("error_digit_only", lang=lang))
        return
    await state.update_data(age=int(message.text))
    await message.answer(await get_text("post_resume_step_3", lang=lang))
    await state.set_state(PostResumeStates.waiting_for_technology)

@router.message(PostResumeStates.waiting_for_technology)
async def resume_tech(message: Message, state: FSMContext):
    await state.update_data(technology=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_resume_step_4", lang=lang))
    await state.set_state(PostResumeStates.waiting_for_telegram)

@router.message(PostResumeStates.waiting_for_telegram)
async def resume_telegram(message: Message, state: FSMContext):
    await state.update_data(telegram_username=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_resume_step_5", lang=lang))
    await state.set_state(PostResumeStates.waiting_for_phone)

@router.message(PostResumeStates.waiting_for_phone)
async def resume_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    await message.answer(await get_text("post_resume_step_6", lang=lang), reply_markup=await get_region_keyboard(user_id))
    await state.set_state(PostResumeStates.waiting_for_region)

@router.callback_query(PostResumeStates.waiting_for_region)
async def resume_region(callback: CallbackQuery, state: FSMContext):
    region = callback.data.replace("region_", "")
    await state.update_data(region=region)
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    msg = await t("post_resume_step_7")
    await callback.message.edit_text(msg.format(region=region))
    await state.set_state(PostResumeStates.waiting_for_salary)

@router.message(PostResumeStates.waiting_for_salary)
async def resume_salary(message: Message, state: FSMContext):
    await state.update_data(salary=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_resume_step_8", lang=lang))
    await state.set_state(PostResumeStates.waiting_for_profession)

@router.message(PostResumeStates.waiting_for_profession)
async def resume_profession(message: Message, state: FSMContext):
    await state.update_data(profession=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_resume_step_9", lang=lang))
    await state.set_state(PostResumeStates.waiting_for_call_time)

@router.message(PostResumeStates.waiting_for_call_time)
async def resume_call_time(message: Message, state: FSMContext):
    await state.update_data(call_time=message.text)
    lang = await get_user_lang(message.from_user.id)
    await message.answer(await get_text("post_resume_step_10", lang=lang))
    await state.set_state(PostResumeStates.waiting_for_goal)

@router.message(PostResumeStates.waiting_for_goal)
async def resume_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    data = await state.get_data()
    
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key, **kwargs): return await get_text(key, lang=lang, **kwargs)
    
    preview_template = await t("post_resume_preview")
    preview = preview_template.format(
        full_name=data.get('full_name'),
        age=data.get('age'),
        technology=data.get('technology'),
        profession=data.get('profession'),
        salary=data.get('salary'),
        region=data.get('region'),
        phone=data.get('phone'),
        telegram=data.get('telegram_username'),
        call_time=data.get('call_time'),
        goal=data.get('goal')
    )
    
    await message.answer(preview, reply_markup=await get_confirm_keyboard("resume", user_id), parse_mode='HTML')
    await state.set_state(PostResumeStates.confirming)

@router.callback_query(F.data == "confirm_resume")
async def confirm_resume(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    async def t(key): return await get_text(key, lang=lang)
    
    try:
        await db.add_resume(
            user_id=user_id,
            full_name=data['full_name'],
            age=data['age'],
            technology=data['technology'],
            telegram_username=data['telegram_username'],
            phone=data['phone'],
            region=data['region'],
            salary=data['salary'],
            profession=data['profession'],
            call_time=data['call_time'],
            goal=data['goal']
        )
        await callback.message.edit_text(await t("post_resume_success"))
    except Exception as e:
        logger.error(f"Error adding resume: {e}")
        await callback.message.edit_text(await t("error_generic"))
    await state.clear()