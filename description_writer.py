import csv
from pathlib import Path
from datetime import datetime

HISTORY_FILE = Path(__file__).parent / "description_history.csv"
COLUMNS = [
    "mode", "sub_mode", "pair", "tp_percent", "sl_percent",
    "risk_to_reward_ratio", "win_rate_percent", "total_pnl_percent",
    "average_pnl_percent", "average_pnl_last_10", "average_hold_hours",
    "tp_hit_count", "sl_hit_count", "manual_close_count",
    "tp_hit_percent", "sl_hit_percent", "manual_close_percent",
    "trade_count", "cv",
]


def init_history():
    if not HISTORY_FILE.exists():
        with open(HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", "asset", "direction"] + COLUMNS + ["description"])


def parse_pasted_row(raw):
    parts = [p.strip() for p in raw.replace("\t", "|").split("|")]
    if len(parts) != len(COLUMNS):
        print(f"\nError: Expected {len(COLUMNS)} values, got {len(parts)}.")
        print(f"Columns expected: {', '.join(COLUMNS)}")
        print(f"Your values: {parts}")
        return None
    return dict(zip(COLUMNS, parts))


def generate_description(data, asset, direction):
    mode = data["mode"]
    sub_mode = data["sub_mode"]
    tp = data["tp_percent"]
    sl = data["sl_percent"]
    rr = data["risk_to_reward_ratio"]
    wr = data["win_rate_percent"]
    total_pnl = data["total_pnl_percent"]
    avg_pnl = data["average_pnl_percent"]
    avg_pnl_10 = data["average_pnl_last_10"]
    avg_hold = data["average_hold_hours"]
    tp_hit_n = data["tp_hit_count"]
    sl_hit_n = data["sl_hit_count"]
    manual_n = data["manual_close_count"]
    tp_hit_p = data["tp_hit_percent"]
    sl_hit_p = data["sl_hit_percent"]
    manual_p = data["manual_close_percent"]
    trades_n = data["trade_count"]
    cv_val = data["cv"]

    direction_upper = direction.upper()
    asset_upper = asset.upper()

    mode_label = {"surprise": "Surprise (Event-Driven)", "candle_colour": "Candle Colour"}.get(mode, mode)
    sub_label = f" ({sub_mode.capitalize()})" if sub_mode and sub_mode != "N/A" else ""

    pnl_sign = "+" if float(total_pnl) >= 0 else ""
    avg_sign = "+" if float(avg_pnl) >= 0 else ""

    tp_f = float(tp)
    sl_f = float(sl)
    rr_f = float(rr)
    wr_f = float(wr)
    total_f = float(total_pnl)
    avg_f = float(avg_pnl)
    avg10_f = float(avg_pnl_10)
    hold_f = float(avg_hold)
    tp_hit_f = float(tp_hit_p)
    sl_hit_f = float(sl_hit_p)
    manual_f = float(manual_p)
    trades_f = float(trades_n)
    cv_f = float(cv_val)

    lines = []
    lines.append(f"# Trading Idea: {direction_upper} {asset_upper}")
    lines.append("")
    lines.append(f"**Strategy:** {mode_label}{sub_label}")
    lines.append(f"**Parameters:** TP = {tp_f:.1f}%, SL = {sl_f:.1f}%")
    lines.append("")
    lines.append("## Performance Summary")
    lines.append(f"- Win Rate: {wr_f:.2f}%")
    lines.append(f"- Risk/Reward Ratio: {rr_f:.2f}")
    lines.append(f"- Total PnL: {pnl_sign}{total_f:.2f}%")
    lines.append(f"- Avg PnL per Trade: {avg_sign}{avg_f:.2f}%")
    lines.append(f"- Avg PnL (Last 10 Trades): {avg_sign}{avg10_f:.2f}%")
    lines.append(f"- Avg Hold Time: {hold_f:.1f} hours")
    lines.append("")
    lines.append("## Trade Distribution")
    lines.append(f"- TP Hit: {tp_hit_f:.2f}% ({int(tp_hit_n)} trades)")
    lines.append(f"- SL Hit: {sl_hit_f:.2f}% ({int(sl_hit_n)} trades)")
    lines.append(f"- Manual Close: {manual_f:.2f}% ({int(manual_n)} trades)")
    lines.append(f"- Total Trades: {int(trades_n)}")
    lines.append(f"- Coefficient of Variation: {cv_f:.4f}")
    lines.append("")

    analysis_parts = []
    if wr_f >= 55:
        analysis_parts.append(f"The strategy delivers a solid {wr_f:.2f}% win rate")
    elif wr_f >= 45:
        analysis_parts.append(f"The strategy maintains a {wr_f:.2f}% win rate")
    else:
        analysis_parts.append(f"The win rate stands at {wr_f:.2f}%")

    if total_f > 5:
        analysis_parts.append(f"with strong total profitability of {pnl_sign}{total_f:.2f}%")
    elif total_f > 0:
        analysis_parts.append(f"with positive total returns of {pnl_sign}{total_f:.2f}%")
    elif total_f == 0:
        analysis_parts.append("with breakeven total returns")
    else:
        analysis_parts.append(f"though total returns are negative at {total_f:.2f}%")

    analysis_parts.append(f"and an average gain of {avg_sign}{avg_f:.2f}% per trade.")

    lines.append("## Analysis")
    lines.append(" ".join(analysis_parts))

    if tp_hit_f > sl_hit_f:
        lines.append(f"TP hits ({tp_hit_f:.2f}%) outpace SL hits ({sl_hit_f:.2f}%), indicating favorable risk-reward execution.")
    elif sl_hit_f > tp_hit_f:
        lines.append(f"SL hits ({sl_hit_f:.2f}%) exceed TP hits ({tp_hit_f:.2f}%), suggesting room for parameter optimization.")
    else:
        lines.append(f"TP and SL hit rates are evenly matched at {tp_hit_f:.2f}% each.")

    lines.append("")
    lines.append(f"*Generated from historical {mode} strategy data - not financial advice.*")

    return "\n".join(lines)


def write_description():
    print("\n" + "=" * 60)
    print("  WRITE A TRADING IDEA DESCRIPTION")
    print("=" * 60)

    print("\nPaste the raw row from Excel (tab-separated values):")
    print(f"  Columns: {', '.join(COLUMNS)}")
    print("  (You can paste multiple lines; only the first non-empty line is used)")
    raw = input("\nPaste here: ").strip()

    data = parse_pasted_row(raw)
    if data is None:
        return

    print(f"\nParsed data for {data['pair']}:")
    print(f"  Mode: {data['mode']} | Sub-mode: {data['sub_mode']}")
    print(f"  Win Rate: {data['win_rate_percent']}% | R:R: {data['risk_to_reward_ratio']}")
    print(f"  Total PnL: {data['total_pnl_percent']}% | Avg PnL: {data['average_pnl_percent']}% | Avg10: {data['average_pnl_last_10']}%")
    print(f"  TP: {data['tp_percent']}% | SL: {data['sl_percent']}% | Trades: {data['trade_count']} | CV: {data['cv']}")

    asset = input(f"\nAsset (default: {data['pair']}): ").strip().upper()
    if not asset:
        asset = data["pair"]

    direction = input("Direction (BUY/SELL): ").strip().upper()
    while direction not in ("BUY", "SELL"):
        direction = input("Must be BUY or SELL: ").strip().upper()

    desc = generate_description(data, asset, direction)

    print("\n" + "-" * 60)
    print("  GENERATED DESCRIPTION")
    print("-" * 60)
    print("\n" + desc + "\n")

    save = input("Save to history? (Y/n): ").strip().lower()
    if save != "n":
        with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), asset, direction]
            row += [data[c] for c in COLUMNS]
            row.append(desc)
            w.writerow(row)
        print("Saved to history.")
    else:
        print("Skipped.")

    input("\nPress Enter to continue...")


def view_history():
    if not HISTORY_FILE.exists():
        print("\nNo history yet.")
        input("\nPress Enter to continue...")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("\nNo entries in history.")
        input("\nPress Enter to continue...")
        return

    print(f"\n{'='*60}")
    print(f"  HISTORY ({len(rows)} entries)")
    print(f"{'='*60}")

    for i, row in enumerate(rows, 1):
        print(f"\n  [{i}] {row['timestamp']} — {row['direction']} {row['asset']}")
        print(f"      Win Rate: {row['win_rate_percent']}% | "
              f"Total PnL: {row['total_pnl_percent']}% | "
              f"Trades: {row['trade_count']}")
        print(f"      TP: {row['tp_percent']}% | SL: {row['sl_percent']}%")

    print()
    choice = input("View full description of entry # (or Enter to skip): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(rows):
            print(f"\n{'='*60}")
            print(rows[idx]["description"])
            print(f"{'='*60}")
        else:
            print("Invalid number.")

    input("\nPress Enter to continue...")


def main():
    init_history()

    while True:
        print("\n" + "=" * 60)
        print("  TRADING IDEA DESCRIPTION WRITER")
        print("=" * 60)
        print("  1. Write a new description")
        print("  2. View history")
        print("  3. Exit")
        print("-" * 60)

        choice = input("Choice: ").strip()

        if choice == "1":
            write_description()
        elif choice == "2":
            view_history()
        elif choice == "3":
            print("Goodbye.")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
