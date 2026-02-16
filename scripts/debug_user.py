import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import db

async def test():
    await db.connect()
    user_id = 1258119183
    u = await db.get_user(user_id)
    f = await db.get_user_filter(user_id)
    p = await db.is_premium(user_id)
    print(f"User: {u}")
    print(f"Filter: {f}")
    print(f"Premium: {p}")
    
    print("\nMost recent vacancies per source:")
    async with db.pool.acquire() as conn:
        rows = await conn.fetch("SELECT source, MAX(published_date) as last_date FROM vacancies GROUP BY source")
        for row in rows:
            print(f"   {row['source']}: {row['last_date']}")
        
        print("\nRecent 'python' vacancies in Tashkent:")
        rows = await conn.fetch("""
            SELECT title, published_date, source 
            FROM vacancies 
            WHERE (title ILIKE '%python%' OR description ILIKE '%python%')
            AND (location ILIKE '%Tashkent%' OR location ILIKE '%Toshkent%')
            ORDER BY published_date DESC LIMIT 5
        """)
        for row in rows:
            print(f"   {row['published_date']} | {row['source']} | {row['title']}")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
