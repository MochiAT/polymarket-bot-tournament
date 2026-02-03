"""Debug why scraped markets aren't being accepted"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.api.gamma_client import GammaClient
from polymarket_bot.api.market_parser import MarketParser
import logging
import json

logging.basicConfig(level=logging.WARNING)

gamma_client = GammaClient(use_web_scraper=True)
parser = MarketParser()

# Get just the scraped markets
updown_markets = gamma_client.get_updown_markets_from_web(max_markets=3)

print("="*100)
print("SCRAPED MARKETS (Raw):")
print("="*100 + "\n")

for i,market in enumerate(updown_markets, 1):
    print(f"{i}. {json.dumps(market, indent=2)}")
    print()

print("="*100)
print("PARSING SCRAPED MARKETS:")
print("="*100 + "\n")

for market in updown_markets:
    print(f"\nMarket ID: {market.get('id')}")
    print(f"Question: {market.get('question')}")
    
    is_valid, reason, parsed = parser.parse_market(market)
    
    print(f"Valid: {is_valid}")
    print(f"Reason: {reason}")
    if parsed:
        print(f"Parsed: {json.dumps(parsed, indent=2, default=str)}")
    print("-"*100)
