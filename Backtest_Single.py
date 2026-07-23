import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from pathlib import Path
from zoneinfo import ZoneInfo
import re
import os

DATA_DIR = Path(".")
OUTPUT_DIR = DATA_DIR / "results"

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

ALL_PAIRS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF",
    "EURJPY", "EURGBP", "EURAUD", "EURNZD", "EURCHF", "EURCAD",
    "GBPJPY", "GBPAUD", "GBPNZD", "GBPCHF", "GBPCAD",
    "AUDJPY", "AUDNZD", "AUDCHF", "AUDCAD",
    "NZDJPY", "NZDCHF", "NZDCAD",
    "CADJPY", "CADCHF", "CHFJPY",
]


def choose_pair():
    print("\nAvailable pairs:")
    for i, p in enumerate(ALL_PAIRS, 1):
        print(f"  {i:2d}. {p}", end="")
        if i % 7 == 0:
            print()
    print()
    choice = input("Type pair name (e.g. GBPUSD) or number: ").strip().upper()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(ALL_PAIRS):
            return ALL_PAIRS[idx]
    if choice in ALL_PAIRS:
        return choice
    print("Invalid pair.")
    return None


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


def choose_entry_time():
    return input("Enter trade entry time in local event timezone HH:MM: ").strip()


def choose_hold_hours():
    while True:
        raw = input("How many hours to hold the trade if TP/SL not hit? ").strip()
        try:
            hours = float(raw)
            if hours > 0:
                return hours
            print("Please enter a positive number.")
        except ValueError:
            print("Invalid number.")


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


def get_cutoff_time(entry_time, hold_hours):
    eow = get_end_of_week_cutoff(entry_time)
    hold_limit = entry_time + pd.Timedelta(hours=hold_hours)
    if hold_limit < eow:
        return hold_limit
    return eow


def simulate_trade_with_offset(df, entry_time, direction, tp_pct, sl_pct, offset_pct, hold_hours):
    """
    offset_pct:
      > 0 means entry offset IN trade direction (stop order style)
      < 0 means entry offset AGAINST trade direction (limit order style)
      0 means exact entry at news candle open

    For long:
      offset > 0: price goes up first, entry is higher, SL wider, TP tighter
      offset < 0: price goes down first, entry is lower, SL tighter, TP wider

    For short:
      offset > 0: price goes down first, entry is lower, SL wider, TP tighter
      offset < 0: price goes up first, entry is higher, SL tighter, TP wider
    """
    if entry_time not in df.index:
        return None

    news_open = float(df.loc[entry_time, "Open"])

    if direction == "long":
        actual_entry_price = news_open * (1 + offset_pct)
        tp_price = actual_entry_price * (1 + tp_pct)
        sl_price = actual_entry_price * (1 - sl_pct)
        trigger_price = news_open * (1 + offset_pct)
        if offset_pct > 0:
            trigger_high = trigger_price
            trigger_low = None
        elif offset_pct < 0:
            trigger_high = None
            trigger_low = trigger_price
        else:
            trigger_high = None
            trigger_low = None
    else:
        actual_entry_price = news_open * (1 - offset_pct)
        tp_price = actual_entry_price * (1 - tp_pct)
        sl_price = actual_entry_price * (1 + sl_pct)
        trigger_price = news_open * (1 - offset_pct)
        if offset_pct > 0:
            trigger_high = None
            trigger_low = trigger_price
        elif offset_pct < 0:
            trigger_high = trigger_price
            trigger_low = None
        else:
            trigger_high = None
            trigger_low = None

    cutoff = get_cutoff_time(entry_time, hold_hours)
    available = df.index[df.index <= cutoff]
    if available.empty:
        return None
    window_end = available[-1]
    window = df.loc[entry_time:window_end]

    if window.empty:
        return None

    order_triggered = offset_pct == 0
    actual_entry_time = entry_time
    actual_entry_price_used = news_open

    for current_time, row in window.iterrows():
        if not order_triggered:
            if direction == "long":
                if trigger_high is not None and row["High"] >= trigger_high:
                    order_triggered = True
                    actual_entry_time = current_time
                    actual_entry_price_used = trigger_high
                    tp_price = actual_entry_price_used * (1 + tp_pct)
                    sl_price = actual_entry_price_used * (1 - sl_pct)
                elif trigger_low is not None and row["Low"] <= trigger_low:
                    order_triggered = True
                    actual_entry_time = current_time
                    actual_entry_price_used = trigger_low
                    tp_price = actual_entry_price_used * (1 + tp_pct)
                    sl_price = actual_entry_price_used * (1 - sl_pct)
            else:
                if trigger_low is not None and row["Low"] <= trigger_low:
                    order_triggered = True
                    actual_entry_time = current_time
                    actual_entry_price_used = trigger_low
                    tp_price = actual_entry_price_used * (1 - tp_pct)
                    sl_price = actual_entry_price_used * (1 + sl_pct)
                elif trigger_high is not None and row["High"] >= trigger_high:
                    order_triggered = True
                    actual_entry_time = current_time
                    actual_entry_price_used = trigger_high
                    tp_price = actual_entry_price_used * (1 - tp_pct)
                    sl_price = actual_entry_price_used * (1 + sl_pct)

            if not order_triggered:
                continue

        if direction == "long":
            tp_hit = row["High"] >= tp_price
            sl_hit = row["Low"] <= sl_price
        else:
            tp_hit = row["Low"] <= tp_price
            sl_hit = row["High"] >= sl_price

        hold_hours = (current_time - actual_entry_time).total_seconds() / 3600

        if tp_hit and sl_hit:
            if SAME_CANDLE_RULE == "sl_first":
                return {
                    "pnl_pct": calculate_pnl(actual_entry_price_used, sl_price, direction),
                    "exit_reason": "SL Hit",
                    "hold_hours": hold_hours,
                    "entry_time": actual_entry_time,
                    "entry_price": actual_entry_price_used,
                    "exit_price": sl_price,
                    "exit_time": current_time,
                    "tp_price": tp_price,
                    "sl_price": sl_price,
                    "order_triggered": True,
                }
            return {
                "pnl_pct": calculate_pnl(actual_entry_price_used, tp_price, direction),
                "exit_reason": "TP Hit",
                "hold_hours": hold_hours,
                "entry_time": actual_entry_time,
                "entry_price": actual_entry_price_used,
                "exit_price": tp_price,
                "exit_time": current_time,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "order_triggered": True,
            }
        if tp_hit:
            return {
                "pnl_pct": calculate_pnl(actual_entry_price_used, tp_price, direction),
                "exit_reason": "TP Hit",
                "hold_hours": hold_hours,
                "entry_time": actual_entry_time,
                "entry_price": actual_entry_price_used,
                "exit_price": tp_price,
                "exit_time": current_time,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "order_triggered": True,
            }
        if sl_hit:
            return {
                "pnl_pct": calculate_pnl(actual_entry_price_used, sl_price, direction),
                "exit_reason": "SL Hit",
                "hold_hours": hold_hours,
                "entry_time": actual_entry_time,
                "entry_price": actual_entry_price_used,
                "exit_price": sl_price,
                "exit_time": current_time,
                "tp_price": tp_price,
                "sl_price": sl_price,
                "order_triggered": True,
            }

    if not order_triggered:
        return {
            "pnl_pct": 0.0,
            "exit_reason": "Order Not Triggered",
            "hold_hours": 0,
            "entry_time": entry_time,
            "entry_price": news_open,
            "exit_price": news_open,
            "exit_time": entry_time,
            "tp_price": 0,
            "sl_price": 0,
            "order_triggered": False,
        }

    manual_exit_price = float(window.iloc[-1]["Close"])
    actual_hold_hours = (window.index[-1] - actual_entry_time).total_seconds() / 3600
    eow = get_end_of_week_cutoff(actual_entry_time)
    exit_reason = "End of Week" if window.index[-1] >= eow - pd.Timedelta(hours=1) else "Hold Time Reached"
    return {
        "pnl_pct": calculate_pnl(actual_entry_price_used, manual_exit_price, direction),
        "exit_reason": exit_reason,
        "hold_hours": actual_hold_hours,
        "entry_time": actual_entry_time,
        "entry_price": actual_entry_price_used,
        "exit_price": manual_exit_price,
        "exit_time": window.index[-1],
        "tp_price": tp_price,
        "sl_price": sl_price,
        "order_triggered": True,
    }


def run_backtest(pair, df, mode, event_currency, news_df, tp_pct, sl_pct, offset_pct, hold_hours, sub_mode=None):
    news_rows = news_df.to_dict("records")
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
            valid_entries.append((entry_time, direction, nr))

    trades = []
    for entry_time, direction, nr in valid_entries:
        trade = simulate_trade_with_offset(df, entry_time, direction, tp_pct, sl_pct, offset_pct, hold_hours)
        if trade is not None:
            trade["direction"] = direction
            trade["news_date"] = nr["History"] if "History" in nr else entry_time
            trade["surprise_type"] = nr.get("Surprise_Type", "neutral")
            trades.append(trade)

    return trades


def summarize_trades(trades, pair, tp, sl, offset, mode, sub_mode):
    trade_count = len(trades)
    if trade_count == 0:
        return None

    pnl_arr = np.array([t["pnl_pct"] for t in trades])
    hold_arr = np.array([t["hold_hours"] for t in trades])
    triggered = [t for t in trades if t["order_triggered"]]
    not_triggered = [t for t in trades if not t["order_triggered"]]

    tp_hit_count = sum(1 for t in triggered if t["exit_reason"] == "TP Hit")
    sl_hit_count = sum(1 for t in triggered if t["exit_reason"] == "SL Hit")
    eow_count = sum(1 for t in triggered if t["exit_reason"] == "End of Week")

    wins = (pnl_arr > 0).sum()
    losses = (pnl_arr < 0).sum()

    return {
        "pair": pair,
        "mode": mode,
        "sub_mode": sub_mode or "N/A",
        "tp_pct": round(tp * 100, 1),
        "sl_pct": round(sl * 100, 1),
        "offset_pct": round(offset * 100, 1),
        "rr_ratio": round(tp / sl, 2) if sl > 0 else 0,
        "trade_count": trade_count,
        "triggered_count": len(triggered),
        "not_triggered_count": len(not_triggered),
        "win_count": int(wins),
        "loss_count": int(losses),
        "win_rate": round(wins / trade_count * 100, 1),
        "total_pnl": round(pnl_arr.sum() * 100, 2),
        "avg_pnl": round(pnl_arr.mean() * 100, 2),
        "avg_pnl_last_10": round(pnl_arr[-10:].mean() * 100, 2) if len(pnl_arr) >= 10 else round(pnl_arr.mean() * 100, 2),
        "best_trade": round(pnl_arr.max() * 100, 2),
        "worst_trade": round(pnl_arr.min() * 100, 2),
        "avg_hold_hours": round(hold_arr.mean(), 1),
        "tp_hit_count": tp_hit_count,
        "sl_hit_count": sl_hit_count,
        "eow_count": eow_count,
        "tp_hit_pct": round(tp_hit_count / trade_count * 100, 1),
        "sl_hit_pct": round(sl_hit_count / trade_count * 100, 1),
        "eow_pct": round(eow_count / trade_count * 100, 1),
    }


def print_summary(stats):
    if stats is None:
        print("\nNo trades to summarize.")
        return
    print("\n" + "=" * 50)
    print("              BACKTEST SUMMARY")
    print("=" * 50)
    for key, val in stats.items():
        print(f"  {key:20s}: {val}")
    print("=" * 50)


def plot_trades_on_chart(df, trades, pair, tp_pct, sl_pct, offset_pct, mode, sub_mode):
    if not trades:
        print("No trades to plot.")
        return

    triggered_trades = [t for t in trades if t["order_triggered"]]
    if not triggered_trades:
        print("No triggered trades to plot.")
        return

    all_entry_times = [t["entry_time"] for t in triggered_trades]
    all_exit_times = [t["exit_time"] for t in triggered_trades]
    min_time = min(all_entry_times)
    max_time = max(all_exit_times)

    buffer_hours = 24
    chart_start = min_time - pd.Timedelta(hours=buffer_hours)
    chart_end = max_time + pd.Timedelta(hours=buffer_hours)

    chart_df = df.loc[chart_start:chart_end].copy()

    if chart_df.empty:
        print("No price data in the chart window.")
        return

    fig, axes = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)

    ax_price = axes[0]
    ax_vol = axes[1]

    ax_price.plot(chart_df.index, chart_df["Close"], color="#333333", linewidth=0.8, alpha=0.6, label="Close")
    ax_price.plot(chart_df.index, chart_df["High"], color="#999999", linewidth=0.3, alpha=0.3)
    ax_price.plot(chart_df.index, chart_df["Low"], color="#999999", linewidth=0.3, alpha=0.3)

    colors = {"long": "#2196F3", "short": "#FF5722"}
    exit_colors = {"TP Hit": "#4CAF50", "SL Hit": "#F44336", "End of Week": "#FF9800", "Order Not Triggered": "#999999"}

    for i, t in enumerate(triggered_trades):
        d = t["direction"]
        c = colors[d]

        ax_price.axhline(y=t["tp_price"], color="#4CAF50", linestyle="--", linewidth=0.6, alpha=0.5)
        ax_price.axhline(y=t["sl_price"], color="#F44336", linestyle="--", linewidth=0.6, alpha=0.5)

        ax_price.plot(t["entry_time"], t["entry_price"], marker="^" if d == "long" else "v",
                      color=c, markersize=10, zorder=5, markeredgecolor="black", markeredgewidth=0.5)

        ec = exit_colors.get(t["exit_reason"], "#999999")
        ax_price.plot(t["exit_time"], t["exit_price"], marker="x", color=ec, markersize=10, zorder=5,
                      markeredgewidth=2)

        ax_price.plot([t["entry_time"], t["exit_time"]], [t["entry_price"], t["exit_price"]],
                      color=c, linewidth=1.2, alpha=0.6, linestyle="-")

        pnl_str = f"{t['pnl_pct']*100:+.2f}%"
        mid_time = t["entry_time"] + (t["exit_time"] - t["entry_time"]) / 2
        mid_price = (t["entry_price"] + t["exit_price"]) / 2
        ax_price.annotate(pnl_str, (mid_time, mid_price), fontsize=7, ha="center",
                          color=c, fontweight="bold",
                          bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor=c))

    title = f"{pair} | TP: {tp_pct*100:.1f}% | SL: {sl_pct*100:.1f}% | Offset: {offset_pct*100:+.1f}%"
    if mode == "candle_colour" and sub_mode:
        title += f" | {sub_mode.upper()}"
    ax_price.set_title(title, fontsize=12, fontweight="bold")
    ax_price.set_ylabel("Price", fontsize=10)
    ax_price.legend(loc="upper left", fontsize=8)
    ax_price.grid(True, alpha=0.3)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#4CAF50", label="TP Hit"),
        Patch(facecolor="#F44336", label="SL Hit"),
        Patch(facecolor="#FF9800", label="End of Week"),
        Patch(facecolor="#2196F3", label="Long Entry"),
        Patch(facecolor="#FF5722", label="Short Entry"),
    ]
    ax_price.legend(handles=legend_elements, loc="upper left", fontsize=8)

    ax_vol.bar(chart_df.index, chart_df["Close"] - chart_df["Open"],
               color=np.where(chart_df["Close"] >= chart_df["Open"], "#4CAF50", "#F44336"),
               width=0.03, alpha=0.4)
    ax_vol.set_ylabel("Candle Body", fontsize=10)
    ax_vol.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.05)

    OUTPUT_DIR.mkdir(exist_ok=True)
    offset_str = f"{offset_pct*100:+.1f}".replace("+", "p").replace("-", "m")
    chart_file = OUTPUT_DIR / f"{pair}_TP{tp_pct*100:.0f}_SL{sl_pct*100:.0f}_OFF{offset_str}.png"
    fig.savefig(chart_file, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"\nChart saved to: {chart_file}")
    plt.show()


def main():
    print("=" * 50)
    print("    SINGLE PAIR BACKTESTER v14")
    print("=" * 50)

    pair = choose_pair()
    if not pair:
        return

    mode = choose_trading_mode()
    if not mode:
        return

    sub_mode = None
    if mode == "candle_colour":
        print("\nSelect Sub-Mode:")
        print("1. Trend (follow candle colour)")
        print("2. Fade (fade candle colour)")
        sub_choice = input("Choice (1/2): ").strip()
        sub_mode = "trend" if sub_choice == "1" else "fade" if sub_choice == "2" else "trend"

    entry_time = choose_entry_time()
    hold_hours = choose_hold_hours()
    inverted_event = choose_inverted_event() if mode == "surprise" else False

    news_df = paste_news_data(pair[:3], entry_time, inverted_event, mode)
    if news_df is None:
        return

    tp_str = input("\nEnter TP in percent (e.g. 0.4): ").strip()
    sl_str = input("Enter SL in percent (e.g. 0.4): ").strip()
    offset_str = input("Enter entry offset in percent (0 = exact, +in direction, -against direction, e.g. 0.1): ").strip()

    try:
        tp_pct = float(tp_str) / 100
        sl_pct = float(sl_str) / 100
        offset_pct = float(offset_str) / 100
    except ValueError:
        print("Invalid number format.")
        return

    if sl_pct <= 0:
        print("SL must be greater than 0.")
        return

    effective_tp = tp_pct + offset_pct if offset_pct < 0 else tp_pct - offset_pct
    effective_sl = sl_pct - offset_pct if offset_pct < 0 else sl_pct + offset_pct
    print(f"\nEffective TP from entry: {effective_tp*100:.2f}%")
    print(f"Effective SL from entry: {effective_sl*100:.2f}%")
    if effective_sl <= 0:
        print("Warning: SL is 0 or negative after offset. Trade may not work correctly.")

    print(f"\nLoading {pair} price data...")
    df = load_csv(pair)
    if df is None:
        return

    event_currency = pair[:3] if mode == "surprise" else pair[:3]

    print(f"\nRunning backtest on {pair}...")
    sub_modes = [sub_mode] if sub_mode else ["trend", "fade"] if mode == "candle_colour" else [None]

    all_trades = []
    for sm in sub_modes:
        trades = run_backtest(pair, df, mode, event_currency, news_df, tp_pct, sl_pct, offset_pct, hold_hours, sub_mode=sm)
        for t in trades:
            t["sub_mode"] = sm
        all_trades.extend(trades)

    stats = summarize_trades(all_trades, pair, tp_pct, sl_pct, offset_pct, mode, sub_mode)
    print_summary(stats)

    if all_trades:
        print(f"\nTotal trades: {len(all_trades)}")
        for i, t in enumerate(all_trades, 1):
            d = t["direction"].upper()
            pnl = t["pnl_pct"] * 100
            reason = t["exit_reason"]
            entry_t = t["entry_time"]
            sm = t.get("sub_mode", "")
            print(f"  {i:3d}. [{d:5s}] {entry_t} | PnL: {pnl:+.2f}% | {reason} | {sm}")

        save = input("\nSave trades to Excel? (y/n): ").strip().lower()
        if save == "y":
            trades_df = pd.DataFrame(all_trades)
            trades_df["pnl_pct"] = trades_df["pnl_pct"] * 100
            trades_df["direction"] = trades_df["direction"]
            OUTPUT_DIR.mkdir(exist_ok=True)
            offset_str_file = f"{offset_pct*100:+.1f}".replace("+", "p").replace("-", "m")
            excel_file = OUTPUT_DIR / f"{pair}_TP{tp_pct*100:.0f}_SL{sl_pct*100:.0f}_OFF{offset_str_file}.xlsx"
            with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
                trades_df.to_excel(writer, sheet_name="Trades", index=False)
                if stats:
                    pd.DataFrame([stats]).to_excel(writer, sheet_name="Summary", index=False)
                news_df.to_excel(writer, sheet_name="News_Used", index=False)
            print(f"Saved to: {excel_file}")

        show_chart = input("\nShow chart? (y/n): ").strip().lower()
        if show_chart == "y":
            plot_trades_on_chart(df, all_trades, pair, tp_pct, sl_pct, offset_pct, mode, sub_mode)
    else:
        print("No trades found.")


if __name__ == "__main__":
    main()
