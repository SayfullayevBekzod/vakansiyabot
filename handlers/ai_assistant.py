from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from utils.i18n import get_text, get_user_lang
from utils.ai_provider import ai_provider
import logging

logger = logging.getLogger(__name__)
router = Router()

class AiAssistantStates(StatesGroup):
    waiting_for_resume = State()
    waiting_for_goal = State()

@router.callback_query(F.data == "ai_skill_gap")
async def start_ai_analysis(callback: CallbackQuery, state: FSMContext):
    """AI Skill Gap Analysis start"""
    lang = await get_user_lang(callback.from_user.id)
    
    # Premium check
    is_premium = await db.is_premium(callback.from_user.id)
    if not is_premium:
        await callback.answer(await get_text("error_premium_required", lang=lang), show_alert=True)
        return

    text = await get_text("ai_analysis_title", lang=lang) + "\n\n"
    text += await get_text("ai_analysis_intro", lang=lang)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await get_text("btn_start_ai", lang=lang), callback_data="ai_proceed_1")],
            [InlineKeyboardButton(text=await get_text("btn_back", lang=lang), callback_data="show_smart")]
        ]
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "ai_proceed_1")
async def ai_check_resume(callback: CallbackQuery, state: FSMContext):
    """Check for existing resume or ask for one"""
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)
    
    # Check resumes table
    resumes = await db.get_resumes(user_id)
    
    if resumes:
        # Use the latest resume
        res = resumes[0]
        resume_text = f"Kasbi: {res['profession']}\nTexnologiyalar: {res['technology']}\nMaqsadi: {res['goal']}"
        await state.update_data(resume_text=resume_text)
        
        await callback.message.edit_text(
            await get_text("ai_ask_goal", lang=lang),
            parse_mode='HTML'
        )
        await state.set_state(AiAssistantStates.waiting_for_goal)
    else:
        # No resume found, ask to send text
        await callback.message.edit_text(
            await get_text("ai_error_no_resume", lang=lang),
            parse_mode='HTML'
        )
        await state.set_state(AiAssistantStates.waiting_for_resume)
    
    await callback.answer()

@router.message(AiAssistantStates.waiting_for_resume)
async def process_ai_resume(message: Message, state: FSMContext):
    """User sent resume as text"""
    lang = await get_user_lang(message.from_user.id)
    await state.update_data(resume_text=message.text)
    
    await message.answer(
        await get_text("ai_ask_goal", lang=lang),
        parse_mode='HTML'
    )
    await state.set_state(AiAssistantStates.waiting_for_goal)

@router.message(AiAssistantStates.waiting_for_goal)
async def process_ai_goal(message: Message, state: FSMContext):
    """User sent their goal, proceed to analysis"""
    lang = await get_user_lang(message.from_user.id)
    data = await state.get_data()
    resume_text = data.get('resume_text')
    goal = message.text
    
    wait_msg = await message.answer(await get_text("ai_analyzing", lang=lang), parse_mode='HTML')
    
    # Call AI
    result = await ai_provider.analyze_skill_gap(resume_text, goal, lang=lang)
    
    await wait_msg.delete()
    
    result_text = await get_text("ai_analysis_result", lang=lang, result=result)
    
    # If result is very long, it might need splitting, but aiogram handles up to 4096. 
    # AI response is usually shorter.
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await get_text("btn_start_ai", lang=lang), callback_data="ai_proceed_1")],
            [InlineKeyboardButton(text=await get_text("btn_back", lang=lang), callback_data="show_smart")]
        ]
    )
    
    if len(result_text) > 4000:
        # Simple split
        parts = [result_text[i:i+4000] for i in range(0, len(result_text), 4000)]
        for part in parts[:-1]:
            await message.answer(part, parse_mode='HTML')
        await message.answer(parts[-1], reply_markup=keyboard, parse_mode='HTML')
    else:
        await message.answer(result_text, reply_markup=keyboard, parse_mode='HTML')
    
    await state.clear()
