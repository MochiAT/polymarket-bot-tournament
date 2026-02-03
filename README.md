# Polymarket Bot Tournament

Read-only Polymarket API integration for paper trading tournament. Supports multiple strategies running in parallel with real-time market data from Polymarket's Gamma and CLOB APIs.

## Features

- ✅ **Read-Only Mode**: No authentication, wallet signing, or real trades
- ✅ **Crypto Binary Markets**: Focuses on BTC, ETH, SOL, XRP intraday markets
- ✅ **Multi-Rate Scheduler**: Fast tick (5-10s) for prices, slow tick (60s) for market refresh
- ✅ **Shared Data Provider**: Singleton pattern prevents API call multiplication across 10+ bots
- ✅ **Paper Trading**: Simulated execution with PnL tracking
- ✅ **Tournament Mode**: Run N strategies in parallel with comprehensive metrics
- ✅ **Abstraction Layers**: Exchange-agnostic strategies, swappable execution engines

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Strategy Layer (N Bots)                   │
├─────────────────────────────────────────────────────────────┤
│         MarketDataProvider (Singleton)                      │
│    ┌──────────────────┐        ┌──────────────────┐        │
│    │  Gamma API       │        │   CLOB API       │        │
│    │  (Markets)       │        │   (Prices)       │        │
│    └──────────────────┘        └──────────────────┘        │
├─────────────────────────────────────────────────────────────┤
│              ExecutionEngine (Paper Trading)                │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
cd "c:\Users\Oscar\Desktop\Coding Projects\OpenClaw\polymarket-bot-tournament"
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Default configuration works out of the box. Optional customization:

```env
# Polling intervals (seconds)
FAST_TICK_INTERVAL=5
SLOW_TICK_INTERVAL=60
MAX_MARKETS_PER_TICK=50

# Candle timeframes (minutes)
CANDLE_TIMEFRAMES=15,60,240,1440

# Logging
LOG_LEVEL=INFO
```

## Usage

### Single Bot

Run one strategy:

```bash
python examples/run_bot.py
```

### Tournament Mode

Run multiple strategies in parallel:

```bash
python examples/run_tournament.py
```

Results are exported to `results/`:
- `leaderboard.csv` - Rankings with PnL, PnL%, PnL/hour, win rate, etc.
- `bots/<name>/trades.csv` - Per-bot trade history
- `bots/<name>/equity.csv` - Equity curve
- `bots/<name>/metrics.json` - Detailed metrics

## Creating Custom Strategies

Inherit from `Strategy` base class:

```python
from polymarket_bot.core.strategy import Strategy
from polymarket_bot.core.market_data import CryptoMarket
from polymarket_bot.core.execution import OrderSide

class MyStrategy(Strategy):
    def on_market_data(self, market: CryptoMarket):
        # Your trading logic here
        if market.implied_probability > 0.7:
            self.execution.place_order(
                market_id=market.market_id,
                side=OrderSide.YES,
                size=10.0,
                price=market.yes_price,
            )
```

## API Details

### Market Scope

The system focuses EXCLUSIVELY on crypto binary markets:
- **Assets**: BTC, ETH, SOL, XRP
- **Format**: "<ASSET> Up or Down – <TIMEFRAME>"
- **Timeframes**: 15 minutes, 1 hour, 4 hours, 1 day
- **Ignored**: Politics, sports, macro, non-price markets

### Data Sources

- **Gamma API** (`gamma-api.polymarket.com`): Market discovery, metadata (status, end_time, resolution)
- **CLOB API** (`clob.polymarket.com`): Live YES/NO pricing, orderbooks, historical prices

### Rate Limiting

- Exponential backoff for 429/500/timeout errors
- Max markets per tick batching with round-robin
- Per-market circuit breakers (mark stale, continue with others)

## Metrics

Tournament leaderboard includes:
- **Net PnL** (absolute and percentage)
- **PnL/Hour** (normalized)
- **Max Drawdown** (peak-to-trough)
- **Win Rate** (winning trades / total trades)
- **Average Hold Time**
- **Trade Count**
- **Exposure Time** (% time in position)

## Error Resilience

- API failures on individual markets don't stop the tournament
- Universe refresh uses diff (new/closed markets only)
- Market validity criteria enforced (active status, future end_time, clobTokenIds present, price_to_beat extractable)

## Project Structure

```
polymarket-bot-tournament/
├── polymarket_bot/
│   ├── api/              # API clients (Gamma, CLOB)
│   ├── core/             # Abstractions (market_data, execution, strategy)
│   ├── execution/        # Paper trading & tournament
│   ├── providers/        # Polymarket provider (singleton)
│   └── config.py         # Configuration
├── examples/
│   ├── simple_strategy.py
│   ├── run_bot.py
│   └── run_tournament.py
├── results/              # Generated tournament results
├── requirements.txt
└── .env.example
```

## License

MIT License
