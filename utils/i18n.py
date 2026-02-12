from locales import uz, ru, en
from database import db
import logging

logger = logging.getLogger(__name__)

# Cache for loaded languages
LANGUAGES = {
    'uz': uz.text,
    'ru': ru.text,
    'en': en.text
}

DEFAULT_LANG = 'uz'

async def get_text(key: str, user_id: int = None, lang: str = None, **kwargs) -> str:
    """
    Get translated text by key.
    Priority:
    1. Explicit `lang` argument
    2. User's language from DB (if `user_id` provided)
    3. Default language ('uz')
    """
    if not lang and user_id:
        lang = await db.get_language(user_id)
    
    lang = lang or DEFAULT_LANG
    
    # Fallback to default if lang not found
    if lang not in LANGUAGES:
        lang = DEFAULT_LANG
        
    texts = LANGUAGES[lang]
    
    # Return text or key if not found
    res = texts.get(key, key)
    if kwargs:
        try:
            return res.format(**kwargs)
        except Exception as e:
            logger.error(f"Error formatting text for key {key}: {e}")
    return res

async def get_user_lang(user_id: int) -> str:
    """Get user language directly"""
    return await db.get_language(user_id)

def get_msg_options(key: str) -> list:
    """
    Get all possible translations for a key to use in filters.
    Returns a list of strings.
    """
    options = set()
    for lang_code in LANGUAGES:
        text = LANGUAGES[lang_code].get(key)
        if text:
            options.add(text)
    return list(options)
