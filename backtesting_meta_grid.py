import numpy as np
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import os

DATA_DIR = Path(".")
OUTPUT_DIR = DATA_DIR / "results"
META_FILE = OUTPUT_DIR / "WINDOW_META_ANALYSIS.xlsx"

TP_VALUES = [x / 1000 for x in range(1, 11)]
SL_VALUES = [x / 1000 for x in range(1, 11)]

SAME_CANDLE_RULE = "sl_first"
ESTIMATED_ROLLOVER_FEE_PERCENT_PER_DAY = 0.01
ROLLOVER_HOUR_UTC = 0

ASSET_TIMEZONES = {
    "USD": "America/New_York", "GBP": "Europe/London", "EUR": "Europe/Berlin",
    "JPY": "Asia/Tokyo", "AUD": "Australia/Sydney", "NZD": "Pacific/Auckland",
    "CHF": "Europe/Zurich", "CAD": "America/Toronto",
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
    return "surprise" if choice == "1" else ("candle_colour" if choice == "2" else None)

def choose_currency_group():
    print("\nAvailable groups:", ", ".join(pair_sets.keys()))
    choice = input("Type currency group (example: GBP): ").upper().strip()
    return choice if choice in pair_sets else None

def choose_entry_time():
    return input("Enter trade entry time in local event timezone HH:MM: ").strip()

def choose_inverted_event():
    print("\nIs higher Actual worse for the currency? (y/n)")
    return input("Choice: ").lower().strip() == "y"

def choose_meta_grid_settings():
    print("\n--- Meta Window Grid Search Settings ---")
    news_name = input("Current News Event Name (e.g., NFP): ").strip() or "Unknown"
    min_train = int(input("Min Train Window Size (default 3): ").strip() or 3)
    max_train = int(input("Max Train Window Size (default 13): ").strip() or 13)
    min_fwd = int(input("Min Forward Test Window Size (default 3): ").strip() or 3)
    max_fwd = int(input("Max Forward Test Window Size (default 13): ").strip() or 13)
    cutoff = float(input("Top Lowest Delta % Cutoff (default 30): ").strip() or 30) / 100.0
    min_wr = float(input("Min Acceptable Win Rate % (default 50): ").strip() or 50.0)
    return news_name, min_train, max_train, min_fwd, max_fwd, cutoff, min_wr

def load_csv(pair):
    file_path = DATA_DIR / f"{pair}_1h.csv"
    if not file_path.exists(): return None
    df = pd.read_csv(file_path, skiprows=[1], engine="c")
    df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True, errors="coerce").dt.tz_localize(None)
    for col in ["Open", "High", "Low", "Close"]: df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Datetime", "Open", "High", "Low", "Close"]).sort_values("Datetime").drop_duplicates("Datetime").set_index("Datetime")

def get_direction(mode, pair, surprise, event_currency, candle=None, sub_mode=None):
    if mode == "surprise":
        if surprise == "neutral": return None
        if pair.startswith(event_currency): return "long" if surprise == "positive" else "short"
        if pair.endswith(event_currency): return "short" if surprise == "positive" else "long"
    elif mode == "candle_colour":
        if candle is None: return None
        candle_colour = "green" if candle["Close"] > candle["Open"] else ("red" if candle["Close"] < candle["Open"] else None)
        if candle_colour is None: return None
        if sub_mode == "trend": return "long" if candle_colour == "green" else "short"
        if sub_mode == "fade": return "short" if candle_colour == "green" else "long"
    return None

def paste_news_data(event_currency, entry_time_str, inverted_event, mode):
    print("\n--- Paste News Data (with header row, then empty line) ---")
    lines = []
    while True:
        line = input()
        if line.strip() == "" and lines: break
        lines.append(line)
    if not lines: return None
    from io import StringIO
    df = pd.read_csv(StringIO("\n".join(lines)), sep="\t")
    if "History" not in df.columns: return None
    def parse_history_date(date_str):
        date_str = re.sub(r'(\w+\s+\d+)-(\d+),\s*(\d{4})', r'\1, \3', str(date_str).strip())
        return pd.to_datetime(date_str, format="%b %d, %Y", errors="coerce")
    df["History"] = df["History"].apply(parse_history_date)
    if mode == "surprise":
        def parse_value(val):
            val = str(val).replace("%", "").replace(",", "").strip().lower()
            return val[:-1] if val.endswith("k") or val.endswith("m") else val
        for col in ["Actual", "Forecast"]: df[col] = pd.to_numeric(df[col].apply(parse_value), errors="coerce")
        df = df.dropna(subset=["History", "Actual", "Forecast"]).copy()
    else: df = df.dropna(subset=["History"]).copy()
    hour, minute = map(int, entry_time_str.split(":"))
    local_tz, utc_tz = ZoneInfo(ASSET_TIMEZONES[event_currency]), ZoneInfo("UTC")
    df["UTC_Time"] = [pd.Timestamp(year=d.year, month=d.month, day=d.day, hour=hour, minute=minute, tz=local_tz).tz_convert(utc_tz).tz_localize(None) for d in df["History"]]
    if mode == "surprise":
        adj = (df["Actual"] - df["Forecast"]) * (-1 if inverted_event else 1)
        df["Surprise_Type"] = adj.apply(lambda v: "positive" if v > 0 else ("negative" if v < 0 else "neutral"))
    else: df["Surprise_Type"] = "neutral"
    return df.sort_values("UTC_Time").reset_index(drop=True)

def build_trade_result(entry_price, exit_price, direction, entry_time, exit_time):
    gross = (exit_price - entry_price) / entry_price if direction == "long" else (entry_price - exit_price) / entry_price
    entry_day = (entry_time - pd.Timedelta(hours=ROLLOVER_HOUR_UTC)).date()
    exit_day = (exit_time - pd.Timedelta(hours=ROLLOVER_HOUR_UTC)).date()
    fee = max(0, (exit_day - entry_day).days) * ESTIMATED_ROLLOVER_FEE_PERCENT_PER_DAY / 100
    return {"pnl_pct": gross - fee, "hold_hours": (exit_time - entry_time).total_seconds() / 3600}

def simulate_trade(df, entry_time, direction, tp_pct, sl_pct):
    if entry_time not in df.index: return None
    entry_price = float(df.loc[entry_time, "Open"])
    tp_p, sl_p = (entry_price*(1+tp_pct), entry_price*(1-sl_pct)) if direction == "long" else (entry_price*(1-tp_pct), entry_price*(1+sl_pct))
    cutoff = (entry_time + pd.Timedelta(days=4-entry_time.weekday())).replace(hour=18, minute=0, second=0, microsecond=0)
    if entry_time.weekday() >= 5 or (entry_time.weekday()==4 and entry_time.hour>=18): cutoff += pd.Timedelta(days=7)
    valid_indices = df.index[df.index <= cutoff]
    if len(valid_indices) == 0: return None
    window = df.loc[entry_time:valid_indices[-1]]
    for t, row in window.iterrows():
        hit_tp = row["High"] >= tp_p if direction=="long" else row["Low"] <= tp_p
        hit_sl = row["Low"] <= sl_p if direction=="long" else row["High"] >= sl_p
        if hit_tp and hit_sl: return build_trade_result(entry_price, sl_p, direction, entry_time, t)
        if hit_tp: return build_trade_result(entry_price, tp_p, direction, entry_time, t)
        if hit_sl: return build_trade_result(entry_price, sl_p, direction, entry_time, t)
    return build_trade_result(entry_price, float(window.iloc[-1]["Close"]), direction, entry_time, window.index[-1])

def calculate_max_drawdown(pnl_series):
    if len(pnl_series) == 0: return 0.0
    cum_pnl = np.cumsum(pnl_series)
    return float(np.max(np.maximum.accumulate(cum_pnl) - cum_pnl))

def main():
    mode = choose_trading_mode()
    group = choose_currency_group()
    entry_time = choose_entry_time()
    inverted = choose_inverted_event() if mode == "surprise" else False
    news_name, min_train, max_train, min_fwd, max_fwd, top_pct_cutoff, min_wr = choose_meta_grid_settings()
    news_df = paste_news_data(group, entry_time, inverted, mode)
    if news_df is None: return
    pair_dfs = {p: df for p in pair_sets[group] if (df := load_csv(p)) is not None}
    if not pair_dfs: return
    news_df = news_df[news_df["UTC_Time"].apply(lambda t: any(t in pdf.index for pdf in pair_dfs.values()))].reset_index(drop=True)
    if mode == "surprise": news_df = news_df[news_df["Surprise_Type"] != "neutral"].reset_index(drop=True)
    elif mode == "candle_colour":
        news_df = news_df[news_df["UTC_Time"].apply(lambda t: any(t in pdf.index and (t-pd.Timedelta(hours=1)) in pdf.index for pdf in pair_dfs.values()))].reset_index(drop=True)
    
    total_events = len(news_df)
    print("\nPre-computing trades...")
    trade_cache = {}
    sub_modes = ["trend", "fade"] if mode == "candle_colour" else ["N/A"]
    for idx, nr in enumerate(news_df.to_dict("records")):
        t_utc = nr["UTC_Time"]
        for pair, pdf in pair_dfs.items():
            if t_utc not in pdf.index: continue
            candle = pdf.loc[t_utc - pd.Timedelta(hours=1)] if mode == "candle_colour" and (t_utc - pd.Timedelta(hours=1)) in pdf.index else None
            for sm in sub_modes:
                dir = get_direction(mode, pair, nr["Surprise_Type"], group, candle, sm if sm != "N/A" else None)
                if dir:
                    for tp in TP_VALUES:
                        for sl in SL_VALUES:
                            if (res := simulate_trade(pdf, t_utc, dir, tp, sl)):
                                trade_cache[(idx, pair, sm, tp, sl)] = {**res, "direction": dir}

    def eval_strat(pair, sm, tp, sl, start, end):
        pnls = [trade_cache[k]["pnl_pct"] for i in range(start, end) if (k := (i, pair, sm, tp, sl)) in trade_cache]
        if not pnls: return {"trade_count": 0, "win_rate": 0.0, "total_pnl": 0.0, "avg_pnl": 0.0}
        return {"trade_count": len(pnls), "win_rate": (np.array(pnls) > 0).mean() * 100, "total_pnl": sum(pnls) * 100, "avg_pnl": np.mean(pnls) * 100}

    strats = [(p, sm, tp, sl) for p in pair_dfs.keys() for sm in sub_modes for tp in TP_VALUES for sl in SL_VALUES]
    all_new_trades = []

    print("\nRunning Window Meta-Grid Sweep...")
    for train_size in range(min_train, max_train + 1):
        for fwd_size in range(min_fwd, max_fwd + 1):
            total_window = train_size + fwd_size
            if total_events < total_window + 1: continue
            num_iters = total_events - total_window
            for i in range(num_iters):
                rows = []
                for p, sm, tp, sl in strats:
                    t_m, f_m = eval_strat(p, sm, tp, sl, i, i + train_size), eval_strat(p, sm, tp, sl, i + train_size, i + total_window)
                    if t_m["trade_count"] > 0 or f_m["trade_count"] > 0:
                        rows.append({"p": p, "sm": sm, "tp": tp, "sl": sl, "rrr": tp/sl, "fwd_avg_pnl": f_m["avg_pnl"], "pnl_delta": abs(t_m["avg_pnl"] - f_m["avg_pnl"]), "train_wr": t_m["win_rate"], "fwd_wr": f_m["win_rate"]})
                if not rows: continue
                df_s = pd.DataFrame(rows).sort_values("pnl_delta").iloc[:max(1, int(np.ceil(len(rows)*top_pct_cutoff)))]
                df_s = df_s.sort_values(["fwd_avg_pnl", "rrr"], ascending=[False, False])
                sel = None
                for _, r in df_s.iterrows():
                    if r["train_wr"] >= min_wr and r["fwd_wr"] >= min_wr:
                        sel = r; break
                if sel is None:
                    for _, r in pd.DataFrame(rows).sort_values(["fwd_avg_pnl", "rrr"], ascending=[False, False]).iterrows():
                        if r["train_wr"] >= min_wr and r["fwd_wr"] >= min_wr:
                            sel = r; break
                target_idx = i + total_window
                if sel is not None and (target_idx, sel["p"], sel["sm"], sel["tp"], sel["sl"]) in trade_cache:
                    pnl = trade_cache[(target_idx, sel["p"], sel["sm"], sel["tp"], sel["sl"])]["pnl_pct"]
                    all_new_trades.append({"News": news_name, "Train_W": train_size, "Fwd_W": fwd_size, "PnL": pnl * 100, "Is_Win": 1 if pnl > 0 else 0})

    if not all_new_trades: return
    new_trades_df = pd.DataFrame(all_new_trades)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Update Database
    if META_FILE.exists():
        master_log = pd.read_excel(META_FILE, sheet_name="Master_Trade_Log")
        master_log = pd.concat([master_log, new_trades_df], ignore_index=True)
    else:
        master_log = new_trades_df

    # Calculate Aggregated Summary from entire Master Log
    summary = []
    for (t_w, f_w), group_df in master_log.groupby(["Train_W", "Fwd_W"]):
        tr = len(group_df)
        news_types = group_df["News"].nunique()
        total_pnl = group_df["PnL"].sum()
        wr = group_df["Is_Win"].mean() * 100
        ev = group_df["PnL"].mean()
        # Drawdown calculation across ALL news events for this window size
        dd = calculate_max_drawdown(group_df["PnL"].values / 100) * 100
        summary.append({"Train_W": t_w, "Fwd_W": f_w, "Total_News_Sources": news_types, "Total_Trades": tr, "Win_Rate_%": wr, "Total_PnL_%": total_pnl, "EV_%": ev, "Max_DD_%": dd})
    
    summary_df = pd.DataFrame(summary).sort_values("Total_PnL_%", ascending=False)

    with pd.ExcelWriter(META_FILE, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Aggregated_Window_Performance", index=False)
        master_log.to_excel(writer, sheet_name="Master_Trade_Log", index=False)
        for sheet_name in writer.sheets:
            writer.sheets[sheet_name].freeze_panes = "A2"

    print(f"\nSuccess! Stacked new results into {META_FILE}")
    print(f"Aggregated table now contains data from {master_log['News'].nunique()} news events.")

if __name__ == "__main__": main()
