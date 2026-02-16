import aiohttp
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class VacancyScraperAPI:
    """hh.uz API orqali vakansiyalarni yig'ish"""
    
    def __init__(self):
        self.base_url = 'https://api.hh.uz'
        self.hosts = [
            'api.hh.uz',
            'api.hh.ru',
            'api.hh.kz',
            'api.hh.by'
        ]
        self.current_host_idx = 0
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
        ]
        
        self.headers = {
            'Accept': 'application/json',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0'
        }
        # Connection pooling uchun session
        self.session = None
        
        # Shahar ID lari
        self.area_ids = {
            'tashkent': '2759',
            'samarkand': '2760',
            'bukhara': '2761',
            'andijan': '2762',
            'fergana': '2763',
            'namangan': '2764',
            'navoi': '2765',
            'kashkadarya': '2766',
            'khorezm': '2767',
            'nukus': '2768',
            'termiz': '2769',
            'jizzakh': '2770',
            'syrdarya': '2771',
            'kokand': '2772'
        }

    def get_random_headers(self):
        """Random User-Agent bilan headerlarni olish"""
        headers = self.headers.copy()
        import random
        headers['User-Agent'] = random.choice(self.user_agents)
        return headers

    def get_next_host(self):
        """Keyingi hostni olish (rotation)"""
        host = self.hosts[self.current_host_idx]
        self.current_host_idx = (self.current_host_idx + 1) % len(self.hosts)
        return f"https://{host}"

    async def get_session(self):
        """Shared session yaratish yoki qaytarish"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self.session = aiohttp.ClientSession(headers=self.headers, timeout=timeout)
        return self.session

    async def close(self):
        """Sessionni yopish"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def scrape_hh_uz(self, keywords: List[str] = None, 
                          location: str = 'Tashkent', 
                          pages: int = 5) -> List[Dict]:
        """hh.uz API dan vakansiyalarni yig'ish"""
        vacancies = []
        
        # Location ID ni aniqlash (dynamic)
        location_lower = location.lower() if location else 'tashkent'
        area_id = self.area_ids.get(location_lower, '2759')  # Default: Tashkent
        
        # Keywords'ni birlashtirish
        search_text = ' '.join(keywords) if keywords else 'python'
        
        logger.info(f"Qidiruv boshlandi: keywords='{search_text}', area={location} ({area_id}), pages={pages}")
        
        session = await self.get_session()
        
        async def fetch_page(page, attempt=0):
            from config import PROXY_URL
            import random
            
            # Har bir so'rov uchun yangi host va headerlar
            base_url = self.get_next_host()
            url = f"{base_url}/vacancies"
            
            params = {
                'text': search_text,
                'area': area_id,
                'page': page,
                'per_page': 50
            }
            
            # Jitter - parallel so'rovlarni biroz kechiktirish
            await asyncio.sleep(random.uniform(0.1, 1.5) * page)
            
            try:
                # Har safar random User-Agent
                headers = self.get_random_headers()
                session = await self.get_session()
                
                async with session.get(
                    url, 
                    params=params, 
                    headers=headers,
                    proxy=PROXY_URL,
                    timeout=aiohttp.ClientTimeout(total=20, connect=7)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('items', [])
                    elif response.status in [403, 429] and attempt < 2:
                        # Blok yoki limit bo'lsa, boshqa host bilan harakat qilish
                        logger.warning(f"HH API {response.status} (host={base_url}). Retrying...")
                        await asyncio.sleep(2 * (attempt + 1))
                        return await fetch_page(page, attempt + 1)
                    else:
                        logger.error(f"API xatolik: Status {response.status}, host={base_url}, page={page}")
                        return []
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"API request error (host={base_url}, page={page}): {e}. Retrying...")
                    await asyncio.sleep(1)
                    return await fetch_page(page, attempt + 1)
                logger.error(f"API request final error (page {page}): {e}")
                return []

        # Parallel fetching
        tasks = [fetch_page(p) for p in range(pages)]
        pages_data = await asyncio.gather(*tasks)
        
        for items in pages_data:
            for item in items:
                try:
                    vacancy = self.parse_vacancy(item)
                    if vacancy:
                        vacancies.append(vacancy)
                except Exception as e:
                    logger.error(f"Item parse xatolik: {e}")
                    continue
        
        logger.info(f"✅ Jami {len(vacancies)} ta vakansiya topildi va parse qilindi")
        return vacancies
    
    def parse_vacancy(self, item: Dict) -> Optional[Dict]:
        """API dan kelgan vakansiyani parse qilish"""
        try:
            # Asosiy ma'lumotlar
            vacancy_id = str(item.get('id', ''))
            title = item.get('name', 'N/A')
            
            if not vacancy_id or not title:
                logger.warning("Vakansiya ID yoki title yo'q")
                return None
            
            # Arxivlangan yoki yopilganligini tekshirish
            if item.get('archived') is True:
                logger.info(f"Vakansiya arxivda: {vacancy_id}")
                return None
                
            if item.get('type', {}).get('id') == 'closed':
                logger.info(f"Vakansiya yopilgan: {vacancy_id}")
                return None
            
            # Kompaniya
            employer = item.get('employer', {})
            company = employer.get('name', 'Noma\'lum')
            
            # Maosh
            salary = item.get('salary')
            salary_min = None
            salary_max = None
            
            if salary:
                salary_min = salary.get('from')
                salary_max = salary.get('to')
                
                # Currency konvertatsiya
                currency = salary.get('currency', 'UZS')
                if currency == 'USD':
                    if salary_min:
                        salary_min = int(salary_min * 12500)
                    if salary_max:
                        salary_max = int(salary_max * 12500)
                elif currency == 'RUR' or currency == 'RUB':
                    if salary_min:
                        salary_min = int(salary_min * 135)
                    if salary_max:
                        salary_max = int(salary_max * 135)
            
            # Joylashuv
            area = item.get('area', {})
            location = area.get('name', 'Tashkent')
            
            # Tavsif (snippet)
            snippet = item.get('snippet', {})
            responsibility = snippet.get('responsibility', '') or ''
            requirement = snippet.get('requirement', '') or ''
            description = f"{responsibility} {requirement}".strip()
            
            # HTML teglarni tozalash
            if description:
                description = description.replace('<highlighttext>', '').replace('</highlighttext>', '')
                description = description.replace('<strong>', '').replace('</strong>', '')
            
            # Tajriba
            experience = item.get('experience', {})
            experience_id = experience.get('id', 'noExperience')
            
            experience_map = {
                'noExperience': 'no_experience',
                'between1And3': 'between_1_and_3',
                'between3And6': 'between_3_and_6',
                'moreThan6': 'more_than_6'
            }
            experience_level = experience_map.get(experience_id, 'not_specified')
            
            # URL
            url = item.get('alternate_url', f"https://hh.uz/vacancy/{vacancy_id}")
            
            # Sana
            published_at = item.get('published_at')
            try:
                if published_at:
                    # ISO format parse qilish
                    dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    # Har doim UTC ga o'tkazish
                    if dt.tzinfo is None:
                        # Agar timezone yo'q bo'lsa, UTC deb qabul qilish
                        published_date = dt.replace(tzinfo=timezone.utc)
                    else:
                        # Agar timezone bor bo'lsa, UTC ga konvert qilish
                        published_date = dt.astimezone(timezone.utc)
                else:
                    published_date = datetime.now(timezone.utc)
            except Exception as e:
                logger.warning(f"Sana parse xatolik: {e}, published_at={published_at}")
                published_date = datetime.now(timezone.utc)
            
            vacancy = {
                'external_id': f"hh_uz_{vacancy_id}",
                'title': title,
                'company': company,
                'description': description,
                'salary_min': salary_min,
                'salary_max': salary_max,
                'location': location,
                'experience_level': experience_level,
                'url': url,
                'source': 'hh_uz',
                'published_date': published_date
            }
            
            return vacancy
            
        except Exception as e:
            logger.error(f"Parse xatolik: {e}", exc_info=True)
            return None

# Global scraper instance
scraper_api = VacancyScraperAPI()


# Test funksiyasi
async def test_api():
    """API scraperni test qilish"""
    print("\n" + "="*70)
    print("🧪 HH.UZ API SCRAPER TEST")
    print("="*70)
    
    keywords = ['python']
    print(f"\n🔍 Qidiruv: {keywords}")
    print(f"📍 Joylashuv: Tashkent")
    print(f"📄 Sahifalar: 2\n")
    
    vacancies = await scraper_api.scrape_hh_uz(keywords=keywords, pages=2)
    
    print(f"\n{'='*70}")
    print(f"✅ NATIJA: {len(vacancies)} ta vakansiya")
    print(f"{'='*70}\n")
    
    if vacancies:
        for i, vac in enumerate(vacancies[:10], 1):
            print(f"📌 {i}. {vac['title']}")
            print(f"   🏢 {vac['company']}")
            
            if vac['salary_min'] or vac['salary_max']:
                print(f"   💰 {vac['salary_min'] or 0:,} - {vac['salary_max'] or '∞'} so'm")
            else:
                print(f"   💰 Maosh ko'rsatilmagan")
            
            print(f"   📍 {vac['location']}")
            print(f"   👔 {vac['experience_level']}")
            print()
        
        if len(vacancies) > 10:
            print(f"... va yana {len(vacancies) - 10} ta vakansiya")
    else:
        print("⚠️  Hech qanday vakansiya parse qilinmadi!")

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(test_api())
    # scraper_api.py