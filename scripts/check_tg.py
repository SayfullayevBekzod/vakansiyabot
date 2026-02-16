import asyncio
import sys
import os
sys.path.append(os.getcwd())
from database import db

async def check():
    await db.connect()
    rows = await db.pool.fetch("SELECT title FROM vacancies WHERE source = 'telegram' LIMIT 20")
    for r in rows:
        print(f"Title: {r['title']}")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
