import pandas as pd
import numpy as np
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from src.config import ASSET_TIMEZONES, SAME_CANDLE_RULE


def load_csv(pair: str, data_dir: Path = Path(".")) -> pd.DataFrame:
    file_path = data_dir / f"{pair}_1h.csv"
    if not file_path.exists():
        raise FileNotFoundError(f"CSV not found for {pair}: {file_path}")
    df = pd.read_csv(file_path, skiprows=[1], engine="c")
    required_cols = ["Datetime", "Open", "High", "Low", "Close"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"{pair} missing columns: {missing_cols}")
    df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True, errors="coerce").dt.tz_localize(None)
    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = (
        df.dropna(subset=required_cols)
        .sort_values("Datetime")
        .drop_duplicates("Datetime")
        .set_index("Datetime")
    )
    return df


def find_entry_candle(df: pd.DataFrame, event_time: pd.Timestamp, entry_hour: int) -> dict:
    target = event_time + pd.Timedelta(hours=entry_hour)
    if target not in df.index:
        idx = df.index.get_indexer([target], method="nearest")[0]
        target = df.index[idx]
    row = df.loc[target]
    color = "green" if row["Close"] > row["Open"] else "red" if row["Close"] < row["Open"] else "doji"
    return {
        "time": target,
        "open": float(row["Open"]),
        "high": float(row["High"]),
        "low": float(row["Low"]),
        "close": float(row["Close"]),
        "color": color,
        "index": df.index.get_loc(target),
    }


def calculate_pnl(entry_price: float, exit_price: float, direction: str) -> float:
    if direction == "long":
        return (exit_price - entry_price) / entry_price
    return (entry_price - exit_price) / entry_price


def get_direction(mode: str, pair: str, surprise: str, event_currency: str,
                  candle: dict = None, sub_mode: str = None) -> str:
    if mode == "surprise":
        if surprise == "neutral":
            return None
        if pair.startswith(event_currency):
            return "long" if surprise == "positive" else "short"
        if pair.endswith(event_currency):
            return "short" if surprise == "positive" else "long"
    elif mode == "candle_colour":
        if candle is None:
            return None
        color = candle["color"]
        if color == "doji":
            return None
        if sub_mode == "trend":
            return "long" if color == "green" else "short"
        if sub_mode == "fade":
            return "short" if color == "green" else "long"
    return None


def simulate_trade(df: pd.DataFrame, entry_time: pd.Timestamp, direction: str,
                   tp_pct: float, sl_pct: float) -> dict:
    if entry_time not in df.index:
        return None
    entry_price = float(df.loc[entry_time, "Open"])
    if direction == "long":
        tp_price = entry_price * (1 + tp_pct)
        sl_price = entry_price * (1 - sl_pct)
    else:
        tp_price = entry_price * (1 - tp_pct)
        sl_price = entry_price * (1 + sl_pct)

    idx = df.index.get_loc(entry_time)
    window = df.iloc[idx:idx + 168]

    if window.empty:
        return None

    positive_hours = 0.0
    negative_hours = 0.0

    for current_time, row in window.iterrows():
        if direction == "long":
            tp_hit = row["High"] >= tp_price
            sl_hit = row["Low"] <= sl_price
        else:
            tp_hit = row["Low"] <= tp_price
            sl_hit = row["High"] >= sl_price

        hold_hours = (current_time - entry_time).total_seconds() / 3600

        if tp_hit and sl_hit:
            if SAME_CANDLE_RULE == "sl_first":
                return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction),
                        "exit_reason": "SL Hit", "hold_hours": hold_hours,
                        "positive_hours": positive_hours, "negative_hours": negative_hours}
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction),
                    "exit_reason": "TP Hit", "hold_hours": hold_hours,
                    "positive_hours": positive_hours, "negative_hours": negative_hours}
        if tp_hit:
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction),
                    "exit_reason": "TP Hit", "hold_hours": hold_hours,
                    "positive_hours": positive_hours, "negative_hours": negative_hours}
        if sl_hit:
            return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction),
                    "exit_reason": "SL Hit", "hold_hours": hold_hours,
                    "positive_hours": positive_hours, "negative_hours": negative_hours}

        if hold_hours > 0:
            close_price = float(row["Close"])
            if direction == "long":
                if close_price > entry_price:
                    positive_hours += 1.0
                elif close_price < entry_price:
                    negative_hours += 1.0
            else:
                if close_price < entry_price:
                    positive_hours += 1.0
                elif close_price > entry_price:
                    negative_hours += 1.0

    manual_exit_price = float(window.iloc[-1]["Close"])
    actual_hold_hours = (window.index[-1] - entry_time).total_seconds() / 3600
    return {"pnl_pct": calculate_pnl(entry_price, manual_exit_price, direction),
            "exit_reason": "End of Week", "hold_hours": actual_hold_hours,
            "positive_hours": positive_hours, "negative_hours": negative_hours}


def grid_search(pair: str, df: pd.DataFrame, mode: str, event_currency: str,
                news_df: pd.DataFrame, sub_mode: str = None) -> pd.DataFrame:
    from src.config import TP_VALUES, SL_VALUES

    results = []
    sub_modes = ["trend", "fade"] if mode == "candle_colour" else [None]
    news_rows = news_df.to_dict("records")

    for sm in sub_modes:
        valid_entries = []
        for nr in news_rows:
            entry_time = nr["UTC_Time"]
            if entry_time not in df.index:
                continue
            candle = None
            if mode == "candle_colour":
                prev_time = entry_time - pd.Timedelta(hours=1)
                if prev_time not in df.index:
                    continue
                candle = df.loc[prev_time].to_dict()
            direction = get_direction(
                mode=mode, pair=pair, surprise=nr["Surprise_Type"],
                event_currency=event_currency, candle=candle, sub_mode=sm,
            )
            if direction is not None:
                valid_entries.append((entry_time, direction))

        for tp in TP_VALUES:
            for sl in SL_VALUES:
                trades = []
                for entry_time, direction in valid_entries:
                    trade = simulate_trade(df, entry_time, direction, tp, sl)
                    if trade is not None:
                        trades.append(trade)
                if trades:
                    pnl_arr = np.array([t["pnl_pct"] for t in trades])
                    trade_count = len(trades)
                    wins = int(round(float((pnl_arr > 0).sum())))
                    losses = trade_count - wins
                    results.append({
                        "mode": mode,
                        "sub_mode": sm or "N/A",
                        "pair": pair,
                        "tp_percent": tp * 100,
                        "sl_percent": sl * 100,
                        "risk_to_reward_ratio": tp / sl,
                        "win_rate_percent": wins / trade_count * 100,
                        "total_pnl_percent": pnl_arr.sum() * 100,
                        "trade_count": trade_count,
                        "wins": wins,
                        "losses": losses,
                    })

    return pd.DataFrame(results) if results else pd.DataFrame()
