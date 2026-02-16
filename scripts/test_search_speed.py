import asyncio
import time
import logging
import sys
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project directory to sys.path
sys.path.append(os.getcwd())

from database import db
from handlers.vacancies import perform_vacancy_search, search_cache
from aiogram.types import Message, User, Chat
from datetime import datetime

class MockMessage:
    def __init__(self, user_id):
        self.from_user = User(id=user_id, is_bot=False, first_name="Test", last_name="User")
        self.chat = Chat(id=user_id, type="private")
        self.message_id = 1
        self.date = datetime.now()
        self.replies = []
        self.message = self # Self-referential for message.delete() etc

    async def answer(self, text, **kwargs):
        print(f"\n[BOT ANSWER]: {text[:200]}...")
        self.replies.append(text)
        return self

    async def delete(self):
        print("[BOT] Message deleted")
        return True

async def test_search():
    try:
        # Initialize DB
        print("Connecting to database...")
        # Ensure pool is initialized
        await db.connect()
        
        if not hasattr(db, 'pool') or db.pool is None:
            print("❌ Failed to initialize database pool.")
            return
        
        # Clear cache for testing
        search_cache.clear()
        print("Cache cleared.")
        
        user_id = 8466568265  # Use a real user ID from logs or a test one
        
        print(f"Setting filters and premium for user {user_id}...")
        await db.save_user_filter(user_id, {
            'keywords': ['Менеджер'],
            'locations': ['Tashkent'],
            'sources': ['telegram', 'user_post']
        })
        await db.set_premium(user_id, 30)
        user_filter = await db.get_user_filter(user_id)
        
        print(f"User filter: {user_filter}")
        print(f"\n🚀 Starting search for user {user_id}...")
        start_time = time.time()
        
        # Mock message
        mock_msg = MockMessage(user_id)
        
        # Perform search
        await perform_vacancy_search(mock_msg, user_id)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n" + "="*50)
        print(f"⏱️ SEARCH DURATION: {duration:.2f} seconds")
        print(f"="*50 + "\n")
        
        if duration < 10:
            print("✅ Performance is acceptable (< 10s)")
        else:
            print("⚠️ Performance might still be slow (> 10s)")

    except Exception as e:
        print(f"❌ Test error: {e}")
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_search())
