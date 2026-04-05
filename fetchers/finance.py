"""财经数据抓取：yfinance → 标准化市场快照。"""
import logging
from datetime import datetime

import yfinance as yf

from config import TICKERS, TZ_CST

logger = logging.getLogger(__name__)

# 各市场分类
MARKET_GROUPS = {
    "us":     ["^GSPC", "^IXIC", "^DJI"],
    "china":  ["000001.SS", "399001.SZ", "399006.SZ", "000688.SS"],
    "hk":     ["^HSI"],
    "metals": ["GC=F", "SI=F", "HG=F", "CL=F"],
    "fx":     ["DX-Y.NYB", "USDCNY=X", "EURUSD=X"],
    "crypto": ["BTC-USD", "ETH-USD"],
}


def fetch_finance() -> dict:
    """返回标准化市场快照字典。"""
    now_cst = datetime.now(TZ_CST)
    results = {}

    for ticker_sym, display_name in TICKERS.items():
        try:
            t = yf.Ticker(ticker_sym)
            info = t.fast_info

            price = _safe(info, "last_price")
            prev  = _safe(info, "previous_close")

            if price is None or prev is None:
                # 回退：取近 5 日历史
                hist = t.history(period="5d", auto_adjust=True)
                if hist.empty:
                    results[ticker_sym] = _empty(display_name, ticker_sym)
                    continue
                price = float(hist["Close"].iloc[-1])
                prev  = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price

            change     = price - prev
            change_pct = change / prev * 100 if prev else 0

            # 近 5 日收盘走势
            hist5 = t.history(period="7d", auto_adjust=True)
            trend = []
            if not hist5.empty:
                trend = [round(float(v), 4) for v in hist5["Close"].tail(5)]

            results[ticker_sym] = {
                "symbol":     ticker_sym,
                "name":       display_name,
                "price":      round(price, 4),
                "change":     round(change, 4),
                "change_pct": round(change_pct, 2),
                "trend5":     trend,
                "market_status": _market_status(ticker_sym, now_cst),
                "currency":   _currency(ticker_sym),
            }
            logger.debug("  %s: %s %+.2f%%", display_name, price, change_pct)

        except Exception as e:
            logger.warning("  %s 数据获取失败: %s", ticker_sym, e)
            results[ticker_sym] = _empty(display_name, ticker_sym)

    return {
        "snapshot_time": now_cst.strftime("%Y-%m-%d %H:%M CST"),
        "tickers": results,
        "groups": MARKET_GROUPS,
    }


def _safe(obj, attr):
    try:
        v = getattr(obj, attr)
        return float(v) if v is not None else None
    except Exception:
        return None


def _empty(name: str, sym: str) -> dict:
    return {
        "symbol": sym, "name": name,
        "price": None, "change": None, "change_pct": None,
        "trend5": [], "market_status": "unknown", "currency": "",
    }


def _market_status(sym: str, now: datetime) -> str:
    """简单判断市场状态（不考虑具体假日，只判断周末和大时段）。"""
    weekday = now.weekday()  # 0=周一 6=周日

    if sym in ("BTC-USD", "ETH-USD"):
        return "open"  # 加密全天开放

    if sym in ["000001.SS", "399001.SZ", "399006.SZ", "000688.SS"]:
        if weekday >= 5:
            return "closed"  # 周末休市
        h = now.hour
        if 9 <= h < 11 or 13 <= h < 15:
            return "open"
        if h == 11 and now.minute < 30:
            return "open"
        return "closed"

    if sym == "^HSI":
        if weekday >= 5:
            return "closed"
        h = now.hour
        if 9 <= h < 16:
            return "open"
        return "closed"

    # 美股：NYSE/NASDAQ 开盘 09:30-16:00 ET，CST = ET+13（标准时）/ET+12（夏令时）
    if sym in ["^GSPC", "^IXIC", "^DJI"]:
        if weekday >= 5:
            return "closed"
        from zoneinfo import ZoneInfo
        now_et = now.astimezone(ZoneInfo("America/New_York"))
        open_min  = now_et.hour * 60 + now_et.minute
        # 09:30 = 570, 16:00 = 960
        if 570 <= open_min < 960:
            return "open"
        return "closed"

    return "unknown"


def _currency(sym: str) -> str:
    if sym in ["000001.SS", "399001.SZ", "399006.SZ", "000688.SS"]:
        return "CNY"
    if sym in ["GC=F", "SI=F", "HG=F", "CL=F", "BTC-USD", "ETH-USD",
               "^GSPC", "^IXIC", "^DJI", "DX-Y.NYB"]:
        return "USD"
    if sym == "^HSI":
        return "HKD"
    if sym == "USDCNY=X":
        return "CNY/USD"
    if sym == "EURUSD=X":
        return "EUR/USD"
    return ""
