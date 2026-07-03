import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_DIR = Path(".")
NEWS_FILE = DATA_DIR / "news.txt"
OUTPUT_EXCEL_FILE = "News_Grid_Search_Results.xlsx"

TP_VALUES = [x / 1000 for x in range(1, 10)]
SL_VALUES = [x / 1000 for x in range(1, 10)]

MAX_HOLD_HOURS = 48
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

    df = pd.read_csv(file_path, skiprows=[1])

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


def load_news_data(event_currency, entry_time_str, inverted_event):
    if not NEWS_FILE.exists():
        print(f"Missing news file: {NEWS_FILE}")
        return None

    try:
        hour, minute = map(int, entry_time_str.split(":"))
    except ValueError:
        print("Invalid time format. Use HH:MM.")
        return None

    df = pd.read_csv(NEWS_FILE, sep="\t")

    for col in ["Actual", "Forecast"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False),
            errors="coerce",
        )

    df["History"] = pd.to_datetime(df["History"], format="%b %d, %Y", errors="coerce")
    df = df.dropna(subset=["History", "Actual", "Forecast"]).copy()

    local_tz = ZoneInfo(ASSET_TIMEZONES[event_currency])
    utc_tz = ZoneInfo("UTC")

    df["UTC_Time"] = [
        pd.Timestamp(
            year=d.year,
            month=d.month,
            day=d.day,
            hour=hour,
            minute=minute,
            tz=local_tz,
        ).tz_convert(utc_tz).tz_localize(None)
        for d in df["History"]
    ]

    adjusted_surprise = (df["Actual"] - df["Forecast"]) * (-1 if inverted_event else 1)

    df["Surprise_Type"] = adjusted_surprise.apply(
        lambda value: "positive" if value > 0 else "negative" if value < 0 else "neutral"
    )

    return df.sort_values("UTC_Time").reset_index(drop=True)


def calculate_pnl(entry_price, exit_price, direction):
    if direction == "long":
        return (exit_price - entry_price) / entry_price
    return (entry_price - exit_price) / entry_price


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

    window = df.loc[entry_time:entry_time + pd.Timedelta(hours=MAX_HOLD_HOURS)]

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
                return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction), "exit_reason": "SL Hit", "hold_hours": hold_hours}
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction), "exit_reason": "TP Hit", "hold_hours": hold_hours}

        if tp_hit:
            return {"pnl_pct": calculate_pnl(entry_price, tp_price, direction), "exit_reason": "TP Hit", "hold_hours": hold_hours}

        if sl_hit:
            return {"pnl_pct": calculate_pnl(entry_price, sl_price, direction), "exit_reason": "SL Hit", "hold_hours": hold_hours}

    manual_exit_price = float(window.iloc[-1]["Close"])
    actual_hold_hours = (window.index[-1] - entry_time).total_seconds() / 3600

    return {"pnl_pct": calculate_pnl(entry_price, manual_exit_price, direction), "exit_reason": "Closed Manually", "hold_hours": actual_hold_hours}


def summarize_trades(trades, mode, sub_mode, pair, tp, sl):
    tdf = pd.DataFrame(trades)

    trade_count = len(tdf)
    tp_hit_count = int((tdf["exit_reason"] == "TP Hit").sum())
    sl_hit_count = int((tdf["exit_reason"] == "SL Hit").sum())
    manual_close_count = int((tdf["exit_reason"] == "Closed Manually").sum())

    return {
        "mode": mode,
        "sub_mode": sub_mode or "N/A",
        "pair": pair,
        "tp_percent": tp * 100,
        "sl_percent": sl * 100,
        "win_rate_percent": (tdf["pnl_pct"] > 0).mean() * 100,
        "total_pnl_percent": tdf["pnl_pct"].sum() * 100,
        "average_pnl_percent": tdf["pnl_pct"].mean() * 100,
        "average_hold_hours": tdf["hold_hours"].mean(),
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

    for sub_mode in sub_modes:
        for tp in TP_VALUES:
            for sl in SL_VALUES:
                trades = []

                for _, news_row in news_df.iterrows():
                    entry_time = news_row["UTC_Time"]

                    if entry_time not in df.index:
                        continue

                    candle = None

                    if mode == "candle_colour":
                        prev_time = entry_time - pd.Timedelta(hours=1)

                        if prev_time not in df.index:
                            continue

                        candle = df.loc[prev_time]

                    direction = get_direction(
                        mode=mode,
                        pair=pair,
                        surprise=news_row["Surprise_Type"],
                        event_currency=event_currency,
                        candle=candle,
                        sub_mode=sub_mode,
                    )

                    if direction is None:
                        continue

                    trade = simulate_trade(df, entry_time, direction, tp, sl)

                    if trade is not None:
                        trades.append(trade)

                if trades:
                    results.append(
                        summarize_trades(
                            trades,
                            mode,
                            sub_mode,
                            pair,
                            tp,
                            sl,
                        )
                    )

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

    news_df = load_news_data(group, entry_time, inverted_event)

    if news_df is None:
        return

    all_results = []

    for pair in pair_sets[group]:
        df = load_csv(pair)

        if df is None:
            continue

        print(f"Processing {pair}...")

        pair_results = grid_search(
            pair,
            df,
            mode,
            group,
            news_df,
        )

        if not pair_results.empty:
            all_results.append(pair_results)

    if not all_results:
        print("No results generated.")
        return

    all_df = pd.concat(all_results, ignore_index=True)

    group_cols = ["pair", "sub_mode"] if mode == "candle_colour" else ["pair"]

    best_df = (
        all_df.sort_values(
            group_cols + ["total_pnl_percent"],
            ascending=[True] * len(group_cols) + [False],
        )
        .groupby(group_cols, as_index=False)
        .first()
    )

    with pd.ExcelWriter(OUTPUT_EXCEL_FILE, engine="openpyxl") as writer:
        best_df.to_excel(writer, sheet_name="Best_Per_Pair", index=False)
        all_df.to_excel(writer, sheet_name="All_Results", index=False)
        news_df.to_excel(writer, sheet_name="News_Used", index=False)

    print(f"\nDone! Results saved to {OUTPUT_EXCEL_FILE}")


if __name__ == "__main__":
    main()
