import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import auto_scrape_and_notify, on_startup, on_shutdown
from database import db

async def test():
    print("🚀 Testing ingestion pipeline...")
    await db.connect()
    
    try:
        # Trigger the scraping logic
        await auto_scrape_and_notify()
        print("✅ Ingestion test completed.")
    except Exception as e:
        print(f"❌ Ingestion test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
