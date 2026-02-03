"""Test robustness improvements"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.api.web_scraper import PolymarketWebScraper
from polymarket_bot.api.gamma_client import GammaClient
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

print("="*100)
print("TESTING ROBUSTNESS IMPROVEMENTS")
print("="*100)

# Test 1: Rate limiting
print("\n1. Testing rate limiting (multiple rapid requests)...")
scraper = PolymarketWebScraper()

start = time.time()
for i in range(5):
    markets = scraper.fetch_updown_market_ids()
    print(f"   Request {i+1}: {len(markets)} markets (elapsed: {time.time() - start:.2f}s)")

print(f"\n   Total time: {time.time() - start:.2f}s (should be >= 2.0s due to rate limiting)")

# Test 2: Caching
print("\n2. Testing cache (requests should be instant)...")
start = time.time()
for i in range(3):
    markets = scraper.fetch_updown_market_ids()
    print(f"   Cached request {i+1}: {len(markets)} markets (elapsed: {time.time() - start:.2f}s)")

# Test 3: Error recovery
print("\n3. Testing error recovery (bad URL)...")
scraper2 = PolymarketWebScraper()
scraper2.CRYPTO_15M_URL = "https://polymarket.com/nonexistent"
markets = scraper2.fetch_updown_market_ids()
print(f"   Result with bad URL: {len(markets)} markets (should return [] gracefully)")

# Test 4: Gamma client integration
print("\n4. Testing full integration with GammaClient...")
gamma_client = GammaClient(use_web_scraper=True)

# Fetch markets (should include scraped ones)
all_markets = gamma_client.get_all_active_markets(max_markets=100, include_updown_scraping=True)
print(f"   Total markets (with scraping): {len(all_markets)}")

# Count Up/Down markets
updown_count = sum(1 for m in all_markets if 'up or down' in (m.get('question', '') or '').lower())
print(f"   Up/Down markets found: {updown_count}")

# Test 5: Cache clearing
print("\n5. Testing cache clear...")
scraper.clear_cache()
print("   Cache cleared successfully")

print("\n" + "="*100)
print("ROBUSTNESS TESTS COMPLETE")
print("="*100)
