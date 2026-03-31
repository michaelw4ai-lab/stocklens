import io
import math
import threading
import time
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import yfinance as yf

_cache = {}
_lock = threading.Lock()

SP500_TTL = 86400  # 24 hours
STOCK_TTL = 900    # 15 minutes


def get_sp500_tickers():
    with _lock:
        if "sp500" in _cache and time.time() - _cache["sp500_time"] < SP500_TTL:
            return _cache["sp500"]

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    df = df[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]]
    # yfinance uses hyphens instead of dots
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)

    with _lock:
        _cache["sp500"] = df
        _cache["sp500_time"] = time.time()
    return df


def get_stock_data():
    with _lock:
        if "stocks" in _cache and time.time() - _cache["stocks_time"] < STOCK_TTL:
            return _cache["stocks"]

    sp500 = get_sp500_tickers()
    tickers = sp500["Symbol"].tolist()

    # Bulk download - 5 days is enough for current price + daily change
    try:
        data = yf.download(tickers, period="5d", group_by="ticker", threads=True)
    except Exception:
        data = pd.DataFrame()

    results = []
    for _, row in sp500.iterrows():
        symbol = row["Symbol"]
        try:
            if len(tickers) == 1:
                ticker_data = data
            else:
                ticker_data = data[symbol]

            closes = ticker_data["Close"].dropna()
            if len(closes) >= 2:
                price = round(float(closes.iloc[-1]), 2)
                prev = float(closes.iloc[-2])
                change = round(price - prev, 2)
                change_pct = round((change / prev) * 100, 2)
            elif len(closes) == 1:
                price = round(float(closes.iloc[-1]), 2)
                change = 0.0
                change_pct = 0.0
            else:
                price = None
                change = None
                change_pct = None
        except Exception:
            price = None
            change = None
            change_pct = None

        results.append({
            "symbol": symbol,
            "name": row["Security"],
            "sector": row["GICS Sector"],
            "sub_industry": row["GICS Sub-Industry"],
            "price": price,
            "change": change,
            "change_pct": change_pct,
        })

    with _lock:
        _cache["stocks"] = results
        _cache["stocks_time"] = time.time()
    return results


def get_dashboard_data():
    stocks = get_stock_data()

    # Sector stats
    sectors = {}
    for s in stocks:
        sec = s["sector"]
        if sec not in sectors:
            sectors[sec] = {"count": 0, "total_change_pct": 0, "valid": 0}
        sectors[sec]["count"] += 1
        if s["change_pct"] is not None:
            sectors[sec]["total_change_pct"] += s["change_pct"]
            sectors[sec]["valid"] += 1

    sector_list = []
    for name, info in sorted(sectors.items()):
        avg = round(info["total_change_pct"] / info["valid"], 2) if info["valid"] > 0 else 0
        sector_list.append({"name": name, "count": info["count"], "avg_change_pct": avg})

    gainers = sum(1 for s in stocks if s["change_pct"] is not None and s["change_pct"] > 0)
    losers = sum(1 for s in stocks if s["change_pct"] is not None and s["change_pct"] < 0)

    return {
        "stocks": stocks,
        "sectors": sector_list,
        "total": len(stocks),
        "gainers": gainers,
        "losers": losers,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_price_history(symbol):
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        dates = [d.strftime("%Y-%m-%d") for d in hist.index]
        prices = [round(float(p), 2) for p in hist["Close"]]
        return {"symbol": symbol, "dates": dates, "prices": prices}
    except Exception:
        return {"symbol": symbol, "dates": [], "prices": []}


def _compute_rsi(prices, period=14):
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _compute_macd(prices):
    prices = np.array(prices, dtype=float)
    ema12 = pd.Series(prices).ewm(span=12).mean().iloc[-1]
    ema26 = pd.Series(prices).ewm(span=26).mean().iloc[-1]
    macd = ema12 - ema26
    signal = pd.Series(
        pd.Series(prices).ewm(span=12).mean() - pd.Series(prices).ewm(span=26).mean()
    ).ewm(span=9).mean().iloc[-1]
    return round(float(macd), 4), round(float(signal), 4)


def _predict_trend(rsi, macd, macd_signal, sma20, sma50, price):
    score = 0
    reasons = []

    # RSI signals
    if rsi < 30:
        score += 2
        reasons.append("RSI oversold (<30) - bullish reversal likely")
    elif rsi < 40:
        score += 1
        reasons.append("RSI approaching oversold - potential upside")
    elif rsi > 70:
        score -= 2
        reasons.append("RSI overbought (>70) - bearish correction likely")
    elif rsi > 60:
        score -= 1
        reasons.append("RSI elevated - momentum slowing")
    else:
        reasons.append("RSI neutral zone")

    # MACD signals
    if macd > macd_signal:
        score += 1
        reasons.append("MACD above signal line - bullish momentum")
    else:
        score -= 1
        reasons.append("MACD below signal line - bearish momentum")

    # Moving average signals
    if price > sma20:
        score += 1
        reasons.append("Price above 20-day SMA - short-term uptrend")
    else:
        score -= 1
        reasons.append("Price below 20-day SMA - short-term downtrend")

    if price > sma50:
        score += 1
        reasons.append("Price above 50-day SMA - medium-term uptrend")
    else:
        score -= 1
        reasons.append("Price below 50-day SMA - medium-term downtrend")

    # Golden/Death cross
    if sma20 > sma50:
        score += 1
        reasons.append("20-day SMA > 50-day SMA - bullish crossover")
    else:
        score -= 1
        reasons.append("20-day SMA < 50-day SMA - bearish crossover")

    if score >= 3:
        outlook = "Strong Bullish"
    elif score >= 1:
        outlook = "Bullish"
    elif score == 0:
        outlook = "Neutral"
    elif score >= -2:
        outlook = "Bearish"
    else:
        outlook = "Strong Bearish"

    return {"outlook": outlook, "score": score, "reasons": reasons}


def get_top10_analysis():
    cache_key = "top10_analysis"
    with _lock:
        if cache_key in _cache and time.time() - _cache[cache_key + "_time"] < STOCK_TTL:
            return _cache[cache_key]

    # Get top 10 by market cap
    top10_symbols = [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
        "META", "BRK-B", "LLY", "AVGO", "TSM"
    ]

    sp500 = get_sp500_tickers()
    sp500_dict = {row["Symbol"]: row for _, row in sp500.iterrows()}

    # Override: use actual S&P 500 top by fetching market caps
    try:
        info_list = []
        for sym in top10_symbols:
            try:
                t = yf.Ticker(sym)
                mcap = t.info.get("marketCap", 0)
                info_list.append((sym, mcap))
            except Exception:
                info_list.append((sym, 0))
        info_list.sort(key=lambda x: x[1], reverse=True)
        top10_symbols = [s[0] for s in info_list[:10]]
    except Exception:
        pass

    results = []
    for symbol in top10_symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Price history (3 months for technical analysis)
            hist = ticker.history(period="3mo")
            if hist.empty:
                continue

            closes = hist["Close"].values.astype(float)
            dates = [d.strftime("%Y-%m-%d") for d in hist.index]
            price = round(float(closes[-1]), 2)

            # Technical indicators
            sma20 = round(float(np.mean(closes[-20:])), 2) if len(closes) >= 20 else price
            sma50 = round(float(np.mean(closes[-50:])), 2) if len(closes) >= 50 else price
            rsi = _compute_rsi(closes) if len(closes) > 14 else 50.0
            macd, macd_signal = _compute_macd(closes) if len(closes) > 26 else (0, 0)

            # Trend prediction
            prediction = _predict_trend(rsi, macd, macd_signal, sma20, sma50, price)

            # Analyst targets
            try:
                targets = ticker.analyst_price_targets
                analyst_data = {
                    "high": targets.get("high"),
                    "low": targets.get("low"),
                    "mean": targets.get("mean"),
                    "median": targets.get("median"),
                    "current": targets.get("current"),
                }
            except Exception:
                analyst_data = None

            # Recommendations
            try:
                recs = ticker.recommendations
                if recs is not None and not recs.empty:
                    latest = recs.iloc[0]
                    rec_data = {
                        "strongBuy": int(latest.get("strongBuy", 0)),
                        "buy": int(latest.get("buy", 0)),
                        "hold": int(latest.get("hold", 0)),
                        "sell": int(latest.get("sell", 0)),
                        "strongSell": int(latest.get("strongSell", 0)),
                    }
                else:
                    rec_data = None
            except Exception:
                rec_data = None

            # News
            try:
                news_raw = ticker.news
                news = []
                for n in (news_raw or [])[:5]:
                    content = n.get("content", {})
                    news.append({
                        "title": content.get("title", ""),
                        "summary": content.get("summary", ""),
                        "provider": content.get("provider", {}).get("displayName", ""),
                        "date": content.get("pubDate", ""),
                        "url": content.get("canonicalUrl", {}).get("url", ""),
                    })
            except Exception:
                news = []

            # Key financials
            market_cap = info.get("marketCap", 0)
            if market_cap >= 1e12:
                market_cap_str = f"${market_cap/1e12:.2f}T"
            elif market_cap >= 1e9:
                market_cap_str = f"${market_cap/1e9:.2f}B"
            else:
                market_cap_str = f"${market_cap/1e6:.0f}M"

            financials = {
                "market_cap": market_cap_str,
                "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else None,
                "forward_pe": round(info.get("forwardPE", 0), 2) if info.get("forwardPE") else None,
                "dividend_yield": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                "52w_high": info.get("fiftyTwoWeekHigh"),
                "52w_low": info.get("fiftyTwoWeekLow"),
                "revenue_growth": round(info.get("revenueGrowth", 0) * 100, 2) if info.get("revenueGrowth") else None,
                "profit_margin": round(info.get("profitMargins", 0) * 100, 2) if info.get("profitMargins") else None,
                "beta": round(info.get("beta", 0), 2) if info.get("beta") else None,
            }

            sp_info = sp500_dict.get(symbol, {})
            name = info.get("shortName") or (sp_info.get("Security", symbol) if isinstance(sp_info, dict) else symbol)
            sector = info.get("sector") or (sp_info.get("GICS Sector", "") if isinstance(sp_info, dict) else "")

            results.append({
                "symbol": symbol,
                "name": name,
                "sector": sector,
                "price": price,
                "dates": dates,
                "prices": [round(float(p), 2) for p in closes],
                "sma20": sma20,
                "sma50": sma50,
                "rsi": rsi,
                "macd": macd,
                "macd_signal": macd_signal,
                "prediction": prediction,
                "analyst": analyst_data,
                "recommendations": rec_data,
                "news": news,
                "financials": financials,
            })
        except Exception as e:
            continue

    with _lock:
        _cache[cache_key] = results
        _cache[cache_key + "_time"] = time.time()
    return results


def refresh_cache():
    with _lock:
        _cache.clear()
