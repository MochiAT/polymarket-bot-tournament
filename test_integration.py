"""Test integrated scraper with Gamma client"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.api.gamma_client import GammaClient
from polymarket_bot.api.market_parser import MarketParser
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

print("="*100)
print("TESTING INTEGRATED GAMMA CLIENT WITH WEB SCRAPER")
print("="*100)

# Create clients
gamma_client = GammaClient(use_web_scraper=True)
parser = MarketParser()

# Fetch markets (should include scraped Up/Down markets)
print("\n1. Fetching all markets (API + Web Scraping)...")
all_markets = gamma_client.get_all_active_markets(max_markets=100, include_updown_scraping=True)

print(f"\nTotal markets fetched: {len(all_markets)}")

# Parse and filter for Up/Down markets
print("\n2. Parsing and filtering Up/Down markets...")
updown_markets = []
for market in all_markets:
    is_valid, reason, parsed = parser.parse_market(market)
    if is_valid:
        updown_markets.append(parsed)

print(f"\n{'='*100}")
print(f"RESULTS: {len(updown_markets)} valid Up/Down markets found!")
print(f"{'='*100}\n")

if updown_markets:
    for i, m in enumerate(updown_markets[:15], 1):
        print(f"{i}. [{m['market_id']}] {m['title'][:80]}")
        print(f"   Asset: {m['asset']} | Timeframe: {m['timeframe']} | Price: ${m.get('price_to_beat', 'N/A')}")
else:
    print("No Up/Down markets found - something went wrong")

print(f"\n{'='*100}")
print("SUCCESS: Bot can now detect Up/Down markets!" if updown_markets else "FAILED")
print(f"{'='*100}")
