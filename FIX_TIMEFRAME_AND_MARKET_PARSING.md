# Fix: Timeframe Parsing & Market Detection (Polymarket Bot Tournament)

## Context
The project `polymarket-bot-tournament` currently filters **all markets out**, resulting in:
```
Scheduler updated with 0 markets
Market <id> discarded: unsupported_timeframe
```

This means the tournament never receives market data.

The root cause is **overly strict parsing** of:
- market titles (Unicode dashes, spacing, casing)
- timeframe formats (15 minutes / 1 hour / etc.)
- fragile matching of "Up or Down" strings

This document defines the **required fixes**.

---

## Goal (Success Criteria)

After applying these changes:

- Running:
  ```bash
  python3 examples/run_bot.py
  ```
  must show:
  ```
  Scheduler updated with X markets
  ```
  where **X > 0**.

- Markets must be crypto binary **“Up or Down”** markets for:
  - BTC, ETH, SOL, XRP
  - timeframes: 15m, 1h, 4h, 1d

- The bot must run without crashing (no `KeyError: equity`).

---

## Required Changes

### 1. Robust Title Normalization (CRITICAL)

Before any parsing or regex, normalize the market title:

- Convert to lowercase
- Replace Unicode dashes:
  - `–` (en dash)
  - `—` (em dash)
  with normal `-`
- Collapse multiple spaces into one
- Trim whitespace

Example:

```
"Bitcoin Up or Down – 15 Minutes"
→ "bitcoin up or down - 15 minutes"
```

All matching must use this `title_norm`.

---

### 2. Flexible “Up or Down” Matching

Do NOT rely on an exact string like `" Up or Down – "`.

Instead:
- Match `"up or down"` anywhere in `title_norm`
- Ignore dash format and spacing

---

### 3. Flexible Asset Detection

Support synonyms (case-insensitive):

- BTC → `btc`, `bitcoin`
- ETH → `eth`, `ethereum`
- SOL → `sol`, `solana`
- XRP → `xrp`

Reject markets without one of these assets.

---

### 4. Robust Timeframe Parsing (MAIN BUG)

Implement a function:

```python
parse_timeframe(title_norm: str, raw_market: dict) -> Optional[str]
```

Accepted timeframes and mappings:

#### 15m
- `15m`
- `15 m`
- `15 min`
- `15 mins`
- `15 minute`
- `15 minutes`
- `15-minute`
- `15-min`

#### 1h
- `1h`
- `1 hour`
- `1 hours`
- `60 min`
- `60 minutes`

#### 4h
- `4h`
- `4 hour`
- `4 hours`
- `240 min`
- `240 minutes`

#### 1d
- `1d`
- `1 day`
- `24 hours`
- `1440 min`
- `1440 minutes`

Mapping output must be **exactly one of**:
```
{"15m", "1h", "4h", "1d"}
```

#### Extraction Priority
1. Explicit fields in market metadata (duration / timeframe / seconds / minutes)
2. Regex on `title_norm`
3. If none found → return `None`

Markets with `None` timeframe must be discarded.

---

### 5. Explicit Discard Logging (MANDATORY)

When discarding a market, log **why**, with context.

Each discard warning MUST include:
- `market_id`
- discard reason
- detected asset (if any)
- extracted timeframe (or `None`)
- original title (truncated to 160 chars)
- normalized title (truncated to 160 chars)

Example log:

```
Market 540844 discarded: unsupported_timeframe
asset=btc timeframe=None
title="Bitcoin Up or Down – 15 Minutes"
title_norm="bitcoin up or down - 15 minutes"
```

To avoid log spam:
- limit to max 30 discard logs per refresh
- aggregate counts per discard reason

---

### 6. Fix Metrics: Always Provide `equity`

In `PaperTradingEngine.get_metrics()`:

- Always return an `equity` key
- Equity must be computed as:
  ```
  equity = initial_cash + realized_pnl + unrealized_pnl
  ```
- If no positions exist:
  - `unrealized_pnl = 0`
- Never return metrics without `equity`

This prevents crashes in:
```
examples/run_bot.py
```

---

## Verification Checklist

After implementation:

1. Run:
   ```bash
   python3 examples/run_bot.py
   ```
2. Confirm:
   - `Scheduler updated with X markets` where X > 0
   - No `unsupported_timeframe` spam without context
   - No `KeyError: equity`
3. Observe:
   - periodic ticks
   - bot stays alive without crashing

---

## Acceptance

This fix is complete only when:
- Markets are successfully parsed and scheduled
- The bot receives live ticks
- The system runs stably in read-only mode
