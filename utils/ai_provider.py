import aiohttp
import logging
from config import GROK_API_KEY

logger = logging.getLogger(__name__)

class GrokProvider:
    def __init__(self):
        self.api_key = GROK_API_KEY
        self.api_url = "https://api.x.ai/v1/chat/completions"

    async def analyze_skill_gap(self, resume_text: str, target_goal: str, lang: str = 'uz') -> str:
        """
        Analyze skill gap using Grok API.
        """
        if not self.api_key:
            logger.error("GROK_API_KEY is not set!")
            return "AI xizmati hozirda ishlamayapti (API key missing)."

        system_prompt = (
            "Siz professional kadrlar bo'yicha maslahatchisiz (HR Expert). "
            "Foydalanuvchining rezyumesini u intilayotgan maqsad (kompaniya yoki lavozim) bilan solishtiring. "
            "Uning kuchli tomonlarini, yetishmayotgan ko'nikmalarini (skill gap) va rivojlanish uchun tavsiyalarni bering. "
            f"Javobni faqat {lang} tilida, chiroyli va tushunarli formatda bering (Markdown va Emoji ishlating)."
        )
        
        if lang == 'ru':
            system_prompt = (
                "Вы профессиональный HR-эксперт. Сравните резюме пользователя с его целью (компанией или должностью). "
                "Выделите сильные стороны, недостающие навыки (skill gap) и дайте рекомендации по развитию. "
                "Дайте ответ только на русском языке в красивом формате (используйте Markdown и Emoji)."
            )
        elif lang == 'en':
            system_prompt = (
                "You are a professional HR Expert. Compare the user's resume with their target goal (company or position). "
                "Highlight strengths, missing skills (skill gap), and provide development recommendations. "
                "Give the answer only in English in a beautiful and clear format (use Markdown and Emojis)."
            )

        prompt = f"REZYUME:\n{resume_text}\n\nMAQSAD: {target_goal}"

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "grok-4-1-fast-reasoning", 
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                }
                
                async with session.post(self.api_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error_text = await response.text()
                        logger.error(f"Grok API Error: {response.status} - {error_text}")
                        return "AI tahlilida xatolik yuz berdi. Iltimos keyinroq urinib ko'ring."
        except Exception as e:
            logger.error(f"Grok Exception: {e}")
            return f"Xatolik: {str(e)}"

ai_provider = GrokProvider()
