import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

async def reauth():
    print("🔐 Telegram Scraper Re-authentication")
    print("------------------------------------")
    
    if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE]):
        print("❌ Error: TELEGRAM_API_ID, API_HASH, or PHONE missing in .env")
        return

    session_name = 'vacancy_bot_session'
    client = TelegramClient(session_name, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    
    print(f"Connecting for phone: {TELEGRAM_PHONE}...")
    await client.start(phone=TELEGRAM_PHONE)
    
    if await client.is_user_authorized():
        print("✅ Success! The session is now authorized.")
        me = await client.get_me()
        print(f"Logged in as: {me.first_name} (@{me.username})")
    else:
        print("❌ Failed to authorize.")
    
    await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(reauth())
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
