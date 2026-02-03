"""Test the web scraper"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.api.web_scraper import PolymarketWebScraper
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

scraper = PolymarketWebScraper()

print("="*100)
print("TESTING WEB SCRAPER FOR UP/DOWN MARKETS")
print("="*100)

# Test 1: Get market slugs
print("\n1. Fetching market slugs...")
slugs = scraper.fetch_updown_market_ids()

print(f"\nFound {len(slugs)} markets:")
for i, market in enumerate(slugs[:10], 1):
    print(f"  {i}. {market['asset']}: {market['slug']}")

# Test 2: Get full details for first 3 markets
print("\n" + "="*100)
print("2. Fetching full market details (first 3)...")
print("="*100)

if slugs:
    markets_with_details = scraper.get_active_updown_markets_with_details(max_markets=3)
    
    print(f"\nSuccessfully fetched {len(markets_with_details)} markets with details:\n")
    
    for i, market in enumerate(markets_with_details, 1):
        print(f"{i}. Market ID: {market.get('market_id')}")
        print(f"   Question: {market.get('question')}")
        print(f"   Asset: {market.get('asset')}")
        print(f"   clobTokenIds: {market.get('clobTokenIds')}")
        print(f"   Slug: {market.get('slug')}")
        print()
    
    # Show full JSON of first market
    if markets_with_details:
        print("="*100)
        print("SAMPLE MARKET (Full JSON):")
        print("="*100)
        print(json.dumps(markets_with_details[0], indent=2))
else:
    print("\nNo markets found to fetch details for")
