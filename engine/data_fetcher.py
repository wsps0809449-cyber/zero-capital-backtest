"""
資料抓取與快取層
- 基金 / ETF 歷史淨值、配息
- 台股 / 美股大盤
- 匯率（當年平均）
設計原則：最小效能、本地 Parquet 快取、增量更新、支援使用者輸入任意標的連網抓取
"""

from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(ticker: str, kind: str = "price") -> Path:
    safe = ticker.replace("^", "").replace("/", "_").replace("=", "_")
    return CACHE_DIR / f"{safe}_{kind}.parquet"


def _safe_read_parquet(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists() or path.stat().st_size < 100:
        return None
    try:
        df = pd.read_parquet(path)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        try:
            path.unlink()
        except Exception:
            pass
        return None


def fetch_price_history(
    ticker: str,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    force: bool = False
) -> pd.DataFrame:
    end = end or datetime.today().strftime("%Y-%m-%d")
    path = _cache_path(ticker, "price")

    if not force:
        df = _safe_read_parquet(path)
        if df is not None:
            df.index = pd.to_datetime(df.index)
            try:
                if df.index.max() >= pd.Timestamp(end) - timedelta(days=7):
                    return df.loc[start:end]
            except Exception:
                pass

    try:
        import yfinance as yf
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df is not None and not df.empty:
            df.to_parquet(path)
            return df
    except Exception as e:
        print(f"[data_fetcher] yfinance 失敗 {ticker}: {e}")

    df = _safe_read_parquet(path)
    if df is not None:
        df.index = pd.to_datetime(df.index)
        return df.loc[start:end] if start else df
    return pd.DataFrame()


def fetch_dividend_history(
    ticker: str,
    start: str = "2010-01-01",
    end: Optional[str] = None,
    force: bool = False
) -> pd.DataFrame:
    end = end or datetime.today().strftime("%Y-%m-%d")
    path = _cache_path(ticker, "div")

    if not force:
        df = _safe_read_parquet(path)
        if df is not None:
            df.index = pd.to_datetime(df.index)
            return df.loc[start:end]

    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        div = t.dividends
        if div is None or div.empty:
            return pd.DataFrame()
        df = div.to_frame(name="Dividends")
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.to_parquet(path)
        return df.loc[start:end]
    except Exception as e:
        print(f"[data_fetcher] 配息抓取失敗 {ticker}: {e}")
        df = _safe_read_parquet(path)
        if df is not None:
            df.index = pd.to_datetime(df.index)
            return df
        return pd.DataFrame()


def fetch_fx_yearly_avg(
    pair: str = "USDTWD=X",
    start_year: int = 2010,
    end_year: Optional[int] = None
) -> Dict[int, float]:
    end_year = end_year or datetime.today().year
    path = _cache_path(pair, "fx_yearly")

    df = _safe_read_parquet(path)
    if df is not None and "rate" in df.columns:
        return {int(k): float(v) for k, v in df["rate"].to_dict().items()}

    try:
        import yfinance as yf
        df = yf.download(pair, start=f"{start_year}-01-01", end=f"{end_year+1}-01-01",
                         progress=False, auto_adjust=True, threads=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df is None or df.empty:
            return {}
        df["year"] = df.index.year
        yearly = df.groupby("year")["Close"].mean()
        out = {int(k): float(v) for k, v in yearly.to_dict().items()}
        pd.DataFrame({"rate": yearly}).to_parquet(path)
        return out
    except Exception as e:
        print(f"[data_fetcher] 匯率抓取失敗 {pair}: {e}")
        return {}


def fetch_index(ticker: str = "^TWII", start: str = "2010-01-01") -> pd.DataFrame:
    return fetch_price_history(ticker, start=start)


KNOWN_TICKERS = {
    "00919": "00919.TW",
    "0056": "0056.TW",
    "S&P500": "^GSPC",
    "台股": "^TWII",
}


if __name__ == "__main__":
    print("Cache dir:", CACHE_DIR)
    df = fetch_index("^GSPC", start="2024-01-01")
    print("^GSPC rows:", len(df))
    print(df.tail(2) if not df.empty else "empty")
