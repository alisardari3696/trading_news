import numpy as np
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
import re

DATA_DIR = Path(".")
OUTPUT_DIR = DATA_DIR / "results"

TP_VALUES = [x / 1000 for x in range(1, 11)]
SL_VALUES = [x / 1000 for x in range(1, 11)]

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
                return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction), "hold_hours": hold_hours}
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction), "hold_hours": hold_hours}
        if tp_hit:
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction), "hold_hours": hold_hours}
        if sl_hit:
            return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction), "hold_hours": hold_hours}

    manual_exit_price = float(window.iloc[-1]["Close"])
    actual_hold_hours = (window.index[-1] - entry_time).total_seconds() / 3600
    return {"pnl_pct": calculate_pnl(entry_price, manual_exit_price, direction), "hold_hours": actual_hold_hours}


def summarize_trades(trades, mode, sub_mode, pair, tp, sl):
    trade_count = len(trades)
    pnl_arr = np.empty(trade_count)
    hold_arr = np.empty(trade_count)
    for i, t in enumerate(trades):
        pnl_arr[i] = t["pnl_pct"]
        hold_arr[i] = t["hold_hours"]
    pnl_mean = pnl_arr.mean()
    pnl_std = pnl_arr.std()
    sharpe_ratio = pnl_mean / pnl_std if pnl_std > 0 else 0.0

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
        "average_hold_hours": hold_arr.mean(),
        "sharpe_ratio": round(sharpe_ratio, 4),
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


METRIC_COLS = [
    "win_rate_percent", "total_pnl_percent", "average_pnl_percent",
    "average_hold_hours", "sharpe_ratio",
]


def merge_train_fwd(train_df, fwd_df, group_cols):
    merged = train_df.merge(
        fwd_df, on=group_cols, suffixes=("_TRAIN", "_FWD"), how="outer",
    )
    for col in METRIC_COLS:
        t_col = f"{col}_TRAIN"
        f_col = f"{col}_FWD"
        if t_col not in merged.columns:
            merged[t_col] = np.nan
        if f_col not in merged.columns:
            merged[f_col] = np.nan
    return merged


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

    pair_dfs = {}
    for pair in pair_sets[group]:
        df = load_csv(pair)
        if df is not None:
            pair_dfs[pair] = df

    if not pair_dfs:
        print("No valid pair data found.")
        return

    total_pasted = len(news_df)

    price_fit_mask = []
    for _, row in news_df.iterrows():
        entry_time_utc = row["UTC_Time"]
        has_price = any(entry_time_utc in pdf.index for pdf in pair_dfs.values())
        price_fit_mask.append(has_price)
    news_df = news_df[price_fit_mask].reset_index(drop=True)
    out_of_range = total_pasted - len(news_df)
    print(f"\nPasted data: {total_pasted}")
    print(f"Out of price data range: {out_of_range}")
    print(f"Fitting price data: {len(news_df)}")

    if mode == "surprise":
        news_df = news_df[news_df["Surprise_Type"] != "neutral"].reset_index(drop=True)
        print(f"Filtered out neutral events. Usable surprise events: {len(news_df)}")
    elif mode == "candle_colour":
        valid_mask = []
        for _, row in news_df.iterrows():
            entry_time_utc = row["UTC_Time"]
            prev_time_utc = entry_time_utc - pd.Timedelta(hours=1)
            is_valid = any(
                entry_time_utc in pdf.index and prev_time_utc in pdf.index
                for pdf in pair_dfs.values()
            )
            valid_mask.append(is_valid)
        news_df = news_df[valid_mask].reset_index(drop=True)
        print(f"Filtered out events with no valid candle. Usable events: {len(news_df)}")

    total_events = len(news_df)
    mid = total_events // 2
    train_news = news_df.iloc[:mid].reset_index(drop=True)
    fwd_news = news_df.iloc[mid:].reset_index(drop=True)

    print(f"\nTotal usable events after all filters: {total_events}")
    print(f"Half: {total_events // 2}")
    print(f"Train (first half): {len(train_news)} events ({train_news['UTC_Time'].iloc[0].date()} to {train_news['UTC_Time'].iloc[-1].date()})")
    print(f"Forward Test (second half): {len(fwd_news)} events ({fwd_news['UTC_Time'].iloc[0].date()} to {fwd_news['UTC_Time'].iloc[-1].date()})")

    print(f"\nRunning {mode} mode on TRAIN and FORWARD TEST splits...")
    all_train_results = []
    all_fwd_results = []

    for pair, df in pair_dfs.items():
        print(f"Processing {pair}...")
        train_results = grid_search(pair, df, mode, group, train_news)
        fwd_results = grid_search(pair, df, mode, group, fwd_news)
        if not train_results.empty:
            all_train_results.append(train_results)
        if not fwd_results.empty:
            all_fwd_results.append(fwd_results)

    if not all_train_results and not all_fwd_results:
        print("No results generated.")
        return

    train_all = pd.concat(all_train_results, ignore_index=True) if all_train_results else pd.DataFrame()
    fwd_all = pd.concat(all_fwd_results, ignore_index=True) if all_fwd_results else pd.DataFrame()

    group_cols = ["mode", "sub_mode", "pair", "tp_percent", "sl_percent", "risk_to_reward_ratio"]

    train_all_sorted = train_all.sort_values("sharpe_ratio", ascending=False) if not train_all.empty else pd.DataFrame(columns=group_cols + METRIC_COLS)
    fwd_all_sorted = fwd_all.sort_values("sharpe_ratio", ascending=False) if not fwd_all.empty else pd.DataFrame(columns=group_cols + METRIC_COLS)

    merged_all = merge_train_fwd(train_all_sorted, fwd_all_sorted, group_cols)
    merged_all.insert(0, "Strategy_ID", range(1, len(merged_all) + 1))
    merged_all["total_pnl_delta"] = (merged_all["total_pnl_percent_TRAIN"] - merged_all["total_pnl_percent_FWD"]).abs()

    ranked = merged_all.sort_values(
        ["pair", "sharpe_ratio_TRAIN"], ascending=[True, False],
    ).reset_index(drop=True)
    ranked.insert(0, "number", range(1, len(ranked) + 1))

    display_cols = ["Strategy_ID"] + group_cols
    for col in METRIC_COLS:
        t_col = f"{col}_TRAIN"
        f_col = f"{col}_FWD"
        if t_col in merged_all.columns:
            display_cols.append(t_col)
        if f_col in merged_all.columns:
            display_cols.append(f_col)
        if col == "total_pnl_percent":
            display_cols.append("total_pnl_delta")
    merged_all = merged_all[[c for c in display_cols if c in merged_all.columns]]

    best_group_cols = ["pair", "sub_mode"] if mode == "candle_colour" else ["pair"]

    best_train = (
        train_all_sorted.sort_values(
            best_group_cols + ["sharpe_ratio"],
            ascending=[True] * len(best_group_cols) + [False],
        )
        .groupby(best_group_cols, as_index=False)
        .first()
    ) if not train_all.empty else pd.DataFrame()

    best_fwd = (
        fwd_all_sorted.sort_values(
            best_group_cols + ["sharpe_ratio"],
            ascending=[True] * len(best_group_cols) + [False],
        )
        .groupby(best_group_cols, as_index=False)
        .first()
    ) if not fwd_all.empty else pd.DataFrame()

    if not best_train.empty and not best_fwd.empty:
        best_merged = merge_train_fwd(best_train, best_fwd, best_group_cols)
    elif not best_train.empty:
        best_merged = best_train.copy()
    else:
        best_merged = best_fwd.copy()

    best_merged.insert(0, "Strategy_ID", range(1, len(best_merged) + 1))
    best_merged["total_pnl_delta"] = (best_merged["total_pnl_percent_TRAIN"] - best_merged["total_pnl_percent_FWD"]).abs()

    best_display = ["Strategy_ID"] + best_group_cols + ["tp_percent", "sl_percent", "risk_to_reward_ratio"]
    for col in METRIC_COLS:
        t_col = f"{col}_TRAIN"
        f_col = f"{col}_FWD"
        if t_col in best_merged.columns:
            best_display.append(t_col)
        if f_col in best_merged.columns:
            best_display.append(f_col)
        if col == "total_pnl_percent":
            best_display.append("total_pnl_delta")
    best_merged = best_merged[[c for c in best_display if c in best_merged.columns]]

    clean_time = entry_time.replace(":", "")
    output_file = f"{group}_{clean_time}_v17.xlsx"
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / output_file

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        best_merged.to_excel(writer, sheet_name="Best_Per_Pair", index=False)
        ranked.to_excel(writer, sheet_name="All_Results", index=False)
        train_news.to_excel(writer, sheet_name="Train_News", index=False)
        fwd_news.to_excel(writer, sheet_name="Fwd_News", index=False)
        for sheet_name in writer.sheets:
            writer.sheets[sheet_name].freeze_panes = "A2"

    print(f"\nDone! Results saved to {output_path}")
    print(f"\n=== Best Strategies (Train vs Forward Test) ===")
    print(best_merged.to_string(index=False))


if __name__ == "__main__":
    main()
