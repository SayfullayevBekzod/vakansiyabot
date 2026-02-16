import asyncio
import sys
import os
sys.path.append(os.getcwd())
from database import db

async def check():
    await db.connect()
    res = await db.pool.fetchval('SELECT count(*) FROM users WHERE user_id = 8466568265')
    print(f'User exists: {res > 0}')
    if res == 0:
        print("Creating test user...")
        await db.add_user(8466568265, "TestUser", "seeker")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
