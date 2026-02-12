from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class VacancyFilter:
    """Vakansiyalarni filtrlash"""
    
    @staticmethod
    def filter_by_keywords(vacancy: Dict, keywords: List[str]) -> bool:
        """Kalit so'zlar bo'yicha filtrlash"""
        if not keywords:
            return True
        
        searchable_text = (
            f"{vacancy.get('title', '')} "
            f"{vacancy.get('description', '')} "
            f"{vacancy.get('company', '')}"
        ).lower()
        
        logger.debug(f"Checking keywords {keywords} in: {searchable_text[:100]}...")
        
        for keyword in keywords:
            if keyword.lower() in searchable_text:
                logger.debug(f"✅ Keyword '{keyword}' found!")
                return True
        
        logger.debug(f"❌ No keywords found")
        return False
    
    @staticmethod
    def filter_by_location(vacancy: Dict, locations: List[str]) -> bool:
        """Joylashuv bo'yicha filtrlash"""
        if not locations:
            return True
        
        vacancy_location = vacancy.get('location', '').lower()
        
        location_map = {
            'tashkent': ['tashkent', 'toshkent', 'ташкент', 'ташкентская область'],
            'samarkand': ['samarkand', 'samarqand', 'самарканд'],
            'bukhara': ['bukhara', 'buxoro', 'бухара'],
            'andijan': ['andijan', 'andijon', 'андижан'],
            'fergana': ['fergana', 'farg\'ona', 'фергана'],
            'namangan': ['namangan', 'наманган'],
            'nukus': ['nukus', 'нукус'],
            'termez': ['termez', 'термез'],
            'qarshi': ['qarshi', 'karshi', 'карши'],
            'gulistan': ['gulistan', 'гулистан'],
            'jizzakh': ['jizzakh', 'jizzax', 'джиззах'],
            'navoiy': ['navoiy', 'navoi', 'навои']
        }
        
        for user_location in locations:
            user_location_lower = user_location.lower()
            
            if user_location_lower in vacancy_location:
                logger.debug(f"✅ Location '{user_location}' found directly!")
                return True
            
            for key, variants in location_map.items():
                if user_location_lower in variants:
                    for variant in variants:
                        if variant in vacancy_location:
                            logger.debug(f"✅ Location '{user_location}' matched via '{variant}'!")
                            return True
        
        logger.debug(f"❌ Location not matched. Vacancy: '{vacancy_location}', User: {locations}")
        return False
    
    @staticmethod
    def filter_by_salary(vacancy: Dict, min_salary: int = None, 
                        max_salary: int = None) -> bool:
        """Maosh bo'yicha filtrlash"""
        vac_min = vacancy.get('salary_min')
        vac_max = vacancy.get('salary_max')
        
        if not vac_min and not vac_max:
            return True
        
        if min_salary:
            if vac_min and vac_min < min_salary:
                return False
            if vac_max and vac_max < min_salary:
                return False
        
        if max_salary:
            if vac_min and vac_min > max_salary:
                return False
        
        return True
    
    @staticmethod
    def filter_by_experience(vacancy: Dict, experience_level: str = None) -> bool:
        """Tajriba darajasi bo'yicha filtrlash"""
        if not experience_level:
            return True
        
        vac_experience = vacancy.get('experience_level', 'not_specified')
        
        if experience_level == vac_experience:
            return True
        
        if experience_level == 'not_specified':
            return True
        
        return False
    
    @staticmethod
    def filter_by_source(vacancy: Dict, user_sources: List[str]) -> bool:
        """Manba bo'yicha filtrlash"""
        if not user_sources:
            return True
            
        vacancy_source = vacancy.get('source', 'hh_uz')
        
        # user_post har doim ko'rinadi (agar manbalardan o'chirilmagan bo'lsa)
        if vacancy_source == 'user_post' and 'user_post' in user_sources:
            return True
            
        return vacancy_source in user_sources

    @staticmethod
    def apply_filters(vacancies: List[Dict], user_filter: Dict) -> List[Dict]:
        """Barcha filtrlarni qo'llash"""
        if not user_filter:
            return vacancies
        
        filtered = []
        user_sources = user_filter.get('sources', ['hh_uz', 'user_post'])
        
        for vacancy in vacancies:
            if not VacancyFilter.filter_by_keywords(
                vacancy, user_filter.get('keywords', [])
            ):
                continue
            
            if not VacancyFilter.filter_by_location(
                vacancy, user_filter.get('locations', [])
            ):
                continue
            
            if not VacancyFilter.filter_by_salary(
                vacancy,
                user_filter.get('salary_min'),
                user_filter.get('salary_max')
            ):
                continue
            
            if not VacancyFilter.filter_by_experience(
                vacancy, user_filter.get('experience_level')
            ):
                continue
                
            if not VacancyFilter.filter_by_source(
                vacancy, user_sources
            ):
                continue
            
            filtered.append(vacancy)
        
        logger.info(f"Filtrlash: {len(vacancies)} -> {len(filtered)}")
        return filtered
    
    @staticmethod
    def format_vacancy_message(vacancy: Dict, lang: str = 'uz') -> str:
        """Vakansiyani xabar formatiga o'tkazish - LOCALIZED"""
        from datetime import datetime, timezone
        from utils.i18n import LANGUAGES
        
        texts = LANGUAGES.get(lang, LANGUAGES['uz'])
        def t(key, **kwargs):
            try:
                text = texts.get(key, key)
                return text.format(**kwargs)
            except Exception as e:
                logger.error(f"Translation error key={{key}}: {{e}}")
                return key

        title = vacancy.get('title', 'N/A')
        company = vacancy.get('company', 'N/A')
        location = vacancy.get('location', 'N/A')
        url = vacancy.get('url', '')
        
        # Maosh
        salary_min = vacancy.get('salary_min')
        salary_max = vacancy.get('salary_max')
        
        if salary_min and salary_max:
            salary = t("vac_salary_range", min=f"{salary_min:,}", max=f"{salary_max:,}")
        elif salary_min:
            salary = t("vac_salary_from", min=f"{salary_min:,}")
        elif salary_max:
            salary = t("vac_salary_to", max=f"{salary_max:,}")
        else:
            salary = t("vac_salary_not_specified")
        
        # Tajriba
        vac_exp = vacancy.get('experience_level', 'not_specified')
        exp_map_keys = {
            'no_experience': "vac_exp_no_experience",
            'between_1_and_3': "vac_exp_between_1_and_3",
            'between_3_and_6': "vac_exp_between_3_and_6",
            'more_than_6': "vac_exp_more_than_6",
            'not_specified': "vac_exp_not_specified"
        }
        experience = t(exp_map_keys.get(vac_exp, "vac_exp_not_specified"))
        
        # E'lon qilingan vaqt
        published_date = vacancy.get('published_date')
        time_ago = t("vac_time_unknown")
        
        if published_date:
            try:
                if isinstance(published_date, datetime):
                    now = datetime.now(timezone.utc)
                    if published_date.tzinfo is None:
                        published_date = published_date.replace(tzinfo=timezone.utc)
                    
                    diff = now - published_date
                    
                    if diff.days > 0:
                        time_ago = t("vac_time_days_ago", days=diff.days)
                    elif diff.seconds >= 3600:
                        hours = diff.seconds // 3600
                        time_ago = t("vac_time_hours_ago", hours=hours)
                    elif diff.seconds >= 60:
                        minutes = diff.seconds // 60
                        time_ago = t("vac_time_minutes_ago", minutes=minutes)
                    else:
                        time_ago = t("vac_time_just_now")
                else:
                    time_ago = str(published_date)[:10]
            except:
                pass
        
        # Tavsif
        description = vacancy.get('description', '')
        if len(description) > 300:
            description = description[:300] + '...'
        
        # ===== MANBA - YAXSHILANGAN =====
        source = vacancy.get('source', 'hh_uz')
        external_id = vacancy.get('external_id', '')
        
        # Telegram kanali nomini olish
        if source == 'telegram' and external_id.startswith('tg_'):
            try:
                # external_id formatini parse: tg_@channel_name_message_id
                parts = external_id.split('_')
                if len(parts) >= 2:
                    channel_name = parts[1]  # @channel_name
                    source_emoji = '📱'
                    source_text = t("vac_source_telegram", channel=channel_name)
                else:
                    source_emoji = '📱'
                    source_text = t("vac_source_telegram_default")
            except:
                source_emoji = '📱'
                source_text = t("vac_source_telegram_default")
        elif source == 'hh_uz':
            source_emoji = '🌐'
            source_text = t("vac_source_hh")
        elif source == 'user_post':
            source_emoji = '📢'
            source_text = t("vac_source_bot")
        else:
            source_emoji = '🔗'
            source_text = source.upper().replace('_', ' ')
        
        # Xabar yaratish
        message = f"""
🔹 <b>{title}</b>

{t('vac_label_company')} {company}
{t('vac_label_salary')} {salary}
{t('vac_label_location')} {location}
{t('vac_label_exp')} {experience}
{t('vac_label_posted')} {time_ago}
{source_emoji} {t('vac_label_source')} {source_text}

{t('vac_label_desc')}
{description}

{t("vac_link_more", url=url)}
"""
        return message.strip()

# Global filter instance
vacancy_filter = VacancyFilter()
