import pandas as pd
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from src.config import ASSET_TIMEZONES


def parse_news_data(raw_data: str, event_currency: str, entry_hour: int,
                    inverted_event: bool = False, mode: str = "surprise") -> pd.DataFrame:
    lines = [line for line in raw_data.strip().split("\n") if line.strip()]
    if not lines:
        return pd.DataFrame()

    from io import StringIO
    df = pd.read_csv(StringIO("\n".join(lines)), sep="\t")

    if "History" not in df.columns:
        return pd.DataFrame()

    def parse_history_date(date_str):
        date_str = str(date_str).strip()
        date_str = re.sub(r'(\w+\s+\d+)-(\d+),\s*(\d{4})', r'\1, \3', date_str)
        return pd.to_datetime(date_str, format="%b %d, %Y", errors="coerce")

    df["History"] = df["History"].astype(str).apply(parse_history_date)

    if mode == "surprise":
        if "Actual" not in df.columns or "Forecast" not in df.columns:
            return pd.DataFrame()

        def parse_value(val):
            val = str(val).replace("%", "").replace(",", "").strip().lower()
            if val.endswith("k") or val.endswith("m"):
                return val[:-1]
            return val

        for col in ["Actual", "Forecast"]:
            df[col] = pd.to_numeric(df[col].astype(str).apply(parse_value), errors="coerce")
        df = df.dropna(subset=["History", "Actual", "Forecast"]).copy()
    else:
        df = df.dropna(subset=["History"]).copy()

    local_tz = ZoneInfo(ASSET_TIMEZONES[event_currency])
    utc_tz = ZoneInfo("UTC")

    df["UTC_Time"] = [
        pd.Timestamp(
            year=d.year, month=d.month, day=d.day,
            hour=entry_hour, minute=0, tz=local_tz,
        ).tz_convert(utc_tz).tz_localize(None)
        for d in df["History"]
    ]

    if mode == "surprise":
        adjusted_surprise = (df["Actual"] - df["Forecast"]) * (-1 if inverted_event else 1)
        df["Surprise_Type"] = adjusted_surprise.apply(
            lambda v: "positive" if v > 0 else "negative" if v < 0 else "neutral"
        )
    else:
        df["Surprise_Type"] = "neutral"

    return df.sort_values("UTC_Time").reset_index(drop=True)


def filter_news_for_surprise(news_df: pd.DataFrame) -> pd.DataFrame:
    return news_df[news_df["Surprise_Type"] != "neutral"].reset_index(drop=True)


def filter_news_for_candle(news_df: pd.DataFrame, pair_dfs: dict) -> pd.DataFrame:
    valid_mask = []
    for _, row in news_df.iterrows():
        entry_time_utc = row["UTC_Time"]
        prev_time_utc = entry_time_utc - pd.Timedelta(hours=1)
        is_valid = any(
            entry_time_utc in pdf.index and prev_time_utc in pdf.index
            for pdf in pair_dfs.values()
        )
        valid_mask.append(is_valid)
    return news_df[valid_mask].reset_index(drop=True)


def filter_by_price_data(news_df: pd.DataFrame, pair_dfs: dict) -> pd.DataFrame:
    valid_mask = []
    for _, row in news_df.iterrows():
        entry_time_utc = row["UTC_Time"]
        has_price = any(entry_time_utc in pdf.index for pdf in pair_dfs.values())
        valid_mask.append(has_price)
    return news_df[valid_mask].reset_index(drop=True)
