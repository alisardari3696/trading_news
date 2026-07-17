import numpy as np
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
import re

DATA_DIR = Path(".")
OUTPUT_DIR = DATA_DIR / "results"

TP_VALUES = [x / 1000 for x in range(2, 12)]
SL_VALUES = [x / 1000 for x in range(2, 12)]

SAME_CANDLE_RULE = "sl_first"

ASSET_TIMEZONES = {
    "USD": "America/New_York",
    "GBP": "Europe/London",
    "EUR": "Europe/Berlin",
    "JPY": "Asia/Tokyo",
    "AUD": "Australia/Sydney",
    "NZD": "Pacific/Auckland",
    "CHF": "Europe/Zurich",
    "CAD": "America/Toronto",
}

pair_sets = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"],
    "EUR": ["EURUSD", "EURJPY", "EURGBP", "EURAUD", "EURNZD", "EURCHF", "EURCAD"],
    "GBP": ["GBPUSD", "GBPJPY", "EURGBP", "GBPAUD", "GBPNZD", "GBPCHF", "GBPCAD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"],
    "AUD": ["AUDUSD", "AUDJPY", "EURAUD", "GBPAUD", "AUDNZD", "AUDCHF", "AUDCAD"],
    "NZD": ["NZDUSD", "NZDJPY", "EURNZD", "GBPNZD", "AUDNZD", "NZDCHF", "NZDCAD"],
    "CHF": ["USDCHF", "EURCHF", "GBPCHF", "AUDCHF", "NZDCHF", "CADCHF", "CHFJPY"],
    "CAD": ["USDCAD", "EURCAD", "GBPCAD", "AUDCAD", "NZDCAD", "CADCHF", "CADJPY"],
}


def choose_trading_mode():
    print("\nSelect Trading Mode:")
    print("1. Surprise (Actual vs Forecast)")
    print("2. Candle Colour (Tests Trend and Fade)")
    choice = input("Choice (1/2): ").strip()
    if choice == "1":
        return "surprise"
    if choice == "2":
        return "candle_colour"
    print("Invalid trading mode.")
    return None


def choose_currency_group():
    print("\nAvailable groups:", ", ".join(pair_sets.keys()))
    choice = input("Type currency group (example: GBP): ").upper().strip()
    if choice in pair_sets:
        return choice
    print("Invalid currency group.")
    return None


def choose_entry_time():
    return input("Enter trade entry time in local event timezone HH:MM: ").strip()


def choose_inverted_event():
    print("\nIs higher Actual worse for the currency? (y/n)")
    choice = input("Choice: ").lower().strip()
    return choice == "y"


def load_csv(pair):
    file_path = DATA_DIR / f"{pair}_1h.csv"
    if not file_path.exists():
        print(f"Missing CSV for {pair}: {file_path}")
        return None
    df = pd.read_csv(file_path, skiprows=[1], engine="c")
    required_cols = ["Datetime", "Open", "High", "Low", "Close"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"{pair} missing columns: {missing_cols}")
        return None
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


def get_direction(mode, pair, surprise, event_currency, candle=None, sub_mode=None):
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
        if candle["Close"] > candle["Open"]:
            candle_colour = "green"
        elif candle["Close"] < candle["Open"]:
            candle_colour = "red"
        else:
            return None
        if sub_mode == "trend":
            return "long" if candle_colour == "green" else "short"
        if sub_mode == "fade":
            return "short" if candle_colour == "green" else "long"
    return None


def paste_news_data(event_currency, entry_time_str, inverted_event, mode):
    print("\n--- Paste News Data ---")
    print("Paste your tab-separated news data below (with header row).")
    print("When done pasting, enter an empty line:\n")
    lines = []
    while True:
        line = input()
        if line.strip() == "" and lines:
            break
        lines.append(line)
    if not lines:
        print("No data pasted.")
        return None
    from io import StringIO
    raw = "\n".join(lines)
    df = pd.read_csv(StringIO(raw), sep="\t")
    if "History" not in df.columns:
        print("Missing 'History' column.")
        return None
    try:
        hour, minute = map(int, entry_time_str.split(":"))
    except ValueError:
        print("Invalid time format. Use HH:MM.")
        return None

    def parse_history_date(date_str):
        date_str = str(date_str).strip()
        date_str = re.sub(r'(\w+\s+\d+)-(\d+),\s*(\d{4})', r'\1, \3', date_str)
        return pd.to_datetime(date_str, format="%b %d, %Y", errors="coerce")

    df["History"] = df["History"].astype(str).apply(parse_history_date)

    if mode == "surprise":
        if "Actual" not in df.columns or "Forecast" not in df.columns:
            print("Surprise mode requires Actual and Forecast columns.")
            return None

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
            hour=hour, minute=minute, tz=local_tz,
        ).tz_convert(utc_tz).tz_localize(None)
        for d in df["History"]
    ]

    if mode == "surprise":
        adjusted_surprise = (df["Actual"] - df["Forecast"]) * (-1 if inverted_event else 1)
        df["Surprise_Type"] = adjusted_surprise.apply(
            lambda value: "positive" if value > 0 else "negative" if value < 0 else "neutral"
        )
    else:
        df["Surprise_Type"] = "neutral"

    return df.sort_values("UTC_Time").reset_index(drop=True)


def calculate_pnl(entry_price, exit_price, direction):
    if direction == "long":
        return (exit_price - entry_price) / entry_price
    return (entry_price - exit_price) / entry_price


def get_end_of_week_cutoff(entry_time):
    days_ahead = 4 - entry_time.weekday()
    if days_ahead < 0 or (days_ahead == 0 and entry_time.hour >= 18):
        days_ahead += 7
    target = entry_time + pd.Timedelta(days=days_ahead)
    return target.replace(hour=18, minute=0, second=0, microsecond=0)


def simulate_trade(df, entry_time, direction, tp_pct, sl_pct):
    if entry_time not in df.index:
        return None
    entry_price = float(df.loc[entry_time, "Open"])
    if direction == "long":
        tp_price = entry_price * (1 + tp_pct)
        sl_price = entry_price * (1 - sl_pct)
    else:
        tp_price = entry_price * (1 - tp_pct)
        sl_price = entry_price * (1 + sl_pct)

    cutoff = get_end_of_week_cutoff(entry_time)
    available = df.index[df.index <= cutoff]
    if available.empty:
        return None
    window_end = available[-1]
    window = df.loc[entry_time:window_end]

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
                return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction), "exit_reason": "SL Hit", "hold_hours": hold_hours, "positive_hours": positive_hours, "negative_hours": negative_hours}
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction), "exit_reason": "TP Hit", "hold_hours": hold_hours, "positive_hours": positive_hours, "negative_hours": negative_hours}
        if tp_hit:
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction), "exit_reason": "TP Hit", "hold_hours": hold_hours, "positive_hours": positive_hours, "negative_hours": negative_hours}
        if sl_hit:
            return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction), "exit_reason": "SL Hit", "hold_hours": hold_hours, "positive_hours": positive_hours, "negative_hours": negative_hours}

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
    return {"pnl_pct": calculate_pnl(entry_price, manual_exit_price, direction), "exit_reason": "End of Week", "hold_hours": actual_hold_hours, "positive_hours": positive_hours, "negative_hours": negative_hours}


def summarize_trades(trades, mode, sub_mode, pair, tp, sl):
    trade_count = len(trades)
    pnl_arr = np.empty(trade_count)
    hold_arr = np.empty(trade_count)
    tp_hit_count = 0
    sl_hit_count = 0
    manual_close_count = 0
    ratios = []
    for i, t in enumerate(trades):
        pnl_arr[i] = t["pnl_pct"]
        hold_arr[i] = t["hold_hours"]
        reason = t["exit_reason"]
        if reason == "TP Hit":
            tp_hit_count += 1
        elif reason == "SL Hit":
            sl_hit_count += 1
        else:
            manual_close_count += 1
        pos = t["positive_hours"]
        neg = t["negative_hours"]
        if neg > 0:
            ratios.append(pos / neg)
        elif pos > 0:
            ratios.append(pos)
        else:
            ratios.append(0.0)
    pnl_mean = pnl_arr.mean()
    last_10_pnl = pnl_arr[-10:].mean() * 100
    mean_ratio = np.mean(ratios) if ratios else 0.0
    return {
        "mode": mode,
        "sub_mode": sub_mode or "N/A",
        "pair": pair,
        "tp_percent": tp * 100,
        "sl_percent": sl * 100,
        "risk_to_reward_ratio": tp / sl,
        "win_rate_percent": float((pnl_arr > 0).sum()) / trade_count * 100,
        "total_pnl_percent": pnl_arr.sum() * 100,
        "average_pnl_percent": pnl_mean * 100,
        "average_pnl_last_10": last_10_pnl,
        "average_hold_hours": hold_arr.mean(),
        "positive_negative_ratio_mean": round(mean_ratio, 2),
        "tp_hit_count": tp_hit_count,
        "sl_hit_count": sl_hit_count,
        "manual_close_count": manual_close_count,
        "tp_hit_percent": tp_hit_count / trade_count * 100,
        "sl_hit_percent": sl_hit_count / trade_count * 100,
        "manual_close_percent": manual_close_count / trade_count * 100,
        "trade_count": trade_count,
    }


def grid_search(pair, df, mode, event_currency, news_df):
    results = []
    sub_modes = ["trend", "fade"] if mode == "candle_colour" else [None]
    news_rows = news_df.to_dict("records")

    for sub_mode in sub_modes:
        valid_entries = []
        for nr in news_rows:
            entry_time = nr["UTC_Time"]
            if entry_time not in df.index:
                continue
            if mode == "candle_colour":
                prev_time = entry_time - pd.Timedelta(hours=1)
                if prev_time not in df.index:
                    continue
                candle = df.loc[prev_time]
            else:
                candle = None
            direction = get_direction(
                mode=mode, pair=pair, surprise=nr["Surprise_Type"],
                event_currency=event_currency, candle=candle, sub_mode=sub_mode,
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
                    results.append(summarize_trades(trades, mode, sub_mode, pair, tp, sl))
    return pd.DataFrame(results)


def main():
    mode = choose_trading_mode()
    if not mode:
        return

    group = choose_currency_group()
    if not group:
        return

    entry_time = choose_entry_time()
    inverted_event = choose_inverted_event() if mode == "surprise" else False

    news_df = paste_news_data(group, entry_time, inverted_event, mode)
    if news_df is None:
        return

    print(f"\nRunning {mode} mode...")
    all_results = []

    for pair in pair_sets[group]:
        df = load_csv(pair)
        if df is None:
            continue
        print(f"Processing {pair}...")
        pair_results = grid_search(pair, df, mode, group, news_df)
        if not pair_results.empty:
            all_results.append(pair_results)

    if not all_results:
        print("No results generated.")
        return

    all_df = pd.concat(all_results, ignore_index=True)
    all_df_sorted = all_df.sort_values("total_pnl_percent", ascending=False)

    group_cols = ["pair", "sub_mode"] if mode == "candle_colour" else ["pair"]

    best_df = (
        all_df_sorted.sort_values(
            group_cols + ["total_pnl_percent"],
            ascending=[True] * len(group_cols) + [False],
        )
        .groupby(group_cols, as_index=False)
        .first()
    )

    clean_time = entry_time.replace(":", "")
    output_file = f"{group}_{clean_time}_v13.xlsx"
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / output_file

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        best_df.to_excel(writer, sheet_name="Best_Per_Pair", index=False)
        all_df_sorted.to_excel(writer, sheet_name="All_Results", index=False)
        news_df.to_excel(writer, sheet_name="News_Used", index=False)
        for sheet_name in writer.sheets:
            writer.sheets[sheet_name].freeze_panes = "A2"

    print(f"\nDone! Results saved to {output_path}")


if __name__ == "__main__":
    main()
