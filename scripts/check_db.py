import asyncio
import sys
import os
sys.path.append(os.getcwd())
from database import db

async def check_db():
    try:
        await db.connect()
        print("Connected to DB.")
        
        # Check counts by source
        rows = await db.pool.fetch('SELECT source, count(*) FROM vacancies GROUP BY source')
        print("\nVacancy counts by source:")
        for row in rows:
            print(f"  {row['source']}: {row['count']} ta")
            
        # Check most recent vacancy date
        latest = await db.pool.fetchval('SELECT MAX(created_at) FROM vacancies')
        print(f"\nLatest vacancy created at: {latest}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_db())
