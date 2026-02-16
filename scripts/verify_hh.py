import asyncio
import time
import logging
import sys
import os
sys.path.append(os.getcwd())
from scraper_api import scraper_api

logging.basicConfig(level=logging.INFO)

async def test_hh():
    print("Testing hh.uz scraper...")
    start = time.time()
    try:
        res = await scraper_api.scrape_hh_uz(keywords=['python'], location='Tashkent', pages=1)
        print(f"Results found: {len(res)}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await scraper_api.close()
    
    print(f"Time taken: {time.time() - start:.2f}s")

if __name__ == "__main__":
    asyncio.run(test_hh())
