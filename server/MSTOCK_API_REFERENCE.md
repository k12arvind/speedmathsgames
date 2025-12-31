# Trading APIs Reference (m.Stock & Zerodha Kite)

---

# Zerodha Kite Connect API Reference

> **Source:** [https://kite.trade/docs/connect/v3/](https://kite.trade/docs/connect/v3/)
> **Developer Portal:** [https://developers.kite.trade](https://developers.kite.trade)
> **Python SDK:** [pykiteconnect](https://github.com/zerodha/pykiteconnect)

## Overview

Kite Connect is a set of REST-like HTTP APIs for building trading and investment platforms.

## Base URLs

| Type | URL |
|------|-----|
| REST API | `https://api.kite.trade` |
| WebSocket | `wss://ws.kite.trade` |

## Pricing

| Plan | Cost | Features |
|------|------|----------|
| Personal | Free | Orders, Portfolio (NO live market data) |
| Connect | ₹500/month | Full API + Live data + Historical data |

## Available Endpoints

### User APIs
- Login/Authentication (OAuth flow)
- User profile
- Margins & Funds

### Orders APIs
- Place/Modify/Cancel orders
- Order history
- Trade book
- GTT (Good Till Triggered) orders

### Portfolio APIs
- **Holdings** - Demat holdings
- **Positions** - Intraday/overnight positions

### Market Data APIs
- **Quote** - Full quote with depth
- **LTP** - Last traded price only
- **OHLC** - Open, High, Low, Close
- **Instruments** - Master list of all tradeable instruments

### Historical Data
- Minute/Day/Week/Month candles
- Custom date ranges

### WebSocket Streaming
- Real-time tick data
- Mode: LTP, Quote, Full

## Quote API Response Fields

```json
{
  "instrument_token": 408065,
  "timestamp": "2024-01-15 09:15:00",
  "last_trade_time": "2024-01-15 09:14:59",
  "last_price": 2450.50,
  "last_quantity": 10,
  "buy_quantity": 50000,
  "sell_quantity": 45000,
  "volume": 1234567,
  "average_price": 2448.25,
  "ohlc": {
    "open": 2440.00,
    "high": 2455.00,
    "low": 2435.00,
    "close": 2438.00
  },
  "net_change": 12.50,
  "depth": {
    "buy": [...],
    "sell": [...]
  }
}
```

## What Kite Connect Does NOT Provide

**Kite Connect is a TRADING API, not a fundamental analysis API.**

❌ ROCE, ROE, P/E Ratio
❌ Market Capitalization
❌ EPS, Book Value
❌ Revenue/Profit data
❌ Financial statements
❌ 3-year growth metrics
❌ Sector classification

## Python SDK Example

```python
from kiteconnect import KiteConnect

kite = KiteConnect(api_key="your_api_key")

# After OAuth login flow
kite.set_access_token("access_token")

# Get quote
quote = kite.quote(["NSE:RELIANCE"])

# Get holdings
holdings = kite.holdings()

# Get historical data
data = kite.historical_data(
    instrument_token=408065,
    from_date="2024-01-01",
    to_date="2024-01-15",
    interval="day"
)
```

---

# m.Stock Trading API Reference

> **Source:** [https://tradingapi.mstock.com/docs/v1/Introduction/](https://tradingapi.mstock.com/docs/v1/Introduction/)
> **Last Updated:** December 31, 2025

## Overview

m.Stock Trading API is a set of REST-like HTTP APIs for building stock market investment and trading platforms. It supports:
- Real-time order execution (equities, derivatives)
- Live market data streaming via WebSockets
- Order status through websockets

## API Types

The API has two types:
- **Type A** - Standard user APIs
- **Type B** - Partner/Extended APIs

## Base URLs

| Type | URL |
|------|-----|
| Interactive (REST) | `https://api.mstock.trade` |
| Broadcasting (WebSocket) | `wss://ws.mstock.trade` |

## Authentication

### Request Headers (Required for all API calls)

```
X-Mirae-Version: 1
Authorization: token api_key:jwtToken
Content-Type: application/json
X-PrivateKey: <your_api_key>
```

### Token Validity

| Token Type | Validity | Note |
|------------|----------|------|
| API Key | 1 year / 1 month / 1 day | Store securely |
| Access Token | Till midnight (same day) | Renew daily |

## Rate Limits

| Limit | Order APIs | Data APIs | Quote APIs | Non-Trading APIs |
|-------|------------|-----------|------------|------------------|
| Per second | 30 | 1 | 20 | - |
| Per minute | 250 | 1000 | Unlimited | Unlimited |
| Per hour | 1000 | 5000 | Unlimited | Unlimited |
| Per day | Unlimited | Unlimited | Unlimited | Unlimited |

## System Maintenance Windows

- **BOD (Beginning of Day):** 07:00 AM - 08:30 AM
- **EOD (End of Day):** 07:00 PM - 09:00 PM

Performance may be affected during these times.

---

## Available API Endpoints

### 1. User APIs
- Login/Authentication
- User profile
- Fund summary

### 2. Orders APIs
- Place orders
- Modify orders
- Cancel orders
- Order history
- Trade book

### 3. Portfolio APIs
- **Holdings** - Get portfolio holdings
- **Positions** - Get current positions

### 4. Calculate Order Margin
- Calculate margin required for orders

### 5. Basket APIs
- Create/manage baskets
- Execute basket orders

### 6. Market Quotes and Instruments
- **Live quotes** for symbols
- Instrument master list
- Symbol search

### 7. Historical Data
- OHLC historical data
- Custom date ranges

### 8. Intraday Chart Data
- Minute-level candle data
- Real-time chart updates

### 9. Option Chain APIs
- Option chain data
- Greeks (Delta, Gamma, etc.)

### 10. Top Gainers/Losers
- Market movers
- Sector-wise gainers/losers

### 11. Data APIs - Market Data
- Index data
- Market status
- Circuit limits

---

## Endpoints We Currently Use

### Authentication
```
POST /openapi/typea/session/verifytotp
Content-Type: application/x-www-form-urlencoded

Body: totp=<code>&api_key=<key>
```

### Holdings
```
GET /openapi/typea/portfolio/holdings
```

### Positions
```
GET /openapi/typea/portfolio/positions
```

### Fund Summary
```
GET /openapi/typea/user/fundsummary
```

### Live Quote
```
GET /openapi/typea/market/quote?exchange=NSE&tradingsymbol=RELIANCE
```

---

## What m.Stock API Does NOT Provide

**The m.Stock API is a TRADING API, not a fundamental analysis API.**

It does NOT provide:
- ❌ ROCE (Return on Capital Employed)
- ❌ ROE (Return on Equity)
- ❌ P/E Ratio
- ❌ EPS
- ❌ Revenue/Profit data
- ❌ 3-year growth metrics
- ❌ Market Cap (directly)
- ❌ Sector classification
- ❌ Financial statements
- ❌ Balance sheet data

**What it DOES provide:**
- ✅ Live stock prices
- ✅ Historical price data (OHLC)
- ✅ Top gainers/losers (by price movement)
- ✅ Your portfolio holdings
- ✅ Order execution

---

## Alternative Data Sources for Fundamentals

For fundamental analysis data (ROCE, ROE, etc.), consider:

1. **Screener.in** - Manual data entry or scraping (no public API)
2. **Tijori Finance** - Paid API for fundamental data
3. **Alpha Vantage** - Limited India coverage
4. **Yahoo Finance** - Basic fundamentals via yfinance Python library
5. **MoneyControl/Economic Times** - Scraping (not recommended)
6. **NSE India** - Limited fundamental data

---

## Configuration File Location

```
~/.mstock_config.json
```

Contains:
- api_key
- totp_secret
- user_name
- user_id
- last_login

---

## Python Client Location

```
/Users/arvind/clat_preparation/server/mstock_client.py
```

## Related Files

- `/Users/arvind/clat_preparation/server/finance_db.py` - Database operations
- `/Users/arvind/clat_preparation/dashboard/finance_stocks.html` - Stock portfolio UI

