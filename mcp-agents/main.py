import logging
import pandas as pd
from pathlib import Path
from src.config import EVENT_TYPES, CURRENCIES, PAIR_SETS
from src.agents.manager import OrchestratorAgent
from src.tools.news_search import (
    parse_news_data, filter_news_for_surprise, filter_news_for_candle,
    filter_by_price_data,
)
from src.tools.excel_writer import create_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 60)
    print("  MCP Trading View Analyzer - Multi-Agent System")
    print("=" * 60)

    print("\nSelect Event Type:")
    for i, event in enumerate(EVENT_TYPES, 1):
        print(f"  {i}. {event}")
    event_choice = int(input("\nChoice (1-9): ")) - 1
    event_type = EVENT_TYPES[event_choice]

    inverted_input = input("\nIs higher actual worse for the currency? (yes/no): ").strip().lower()
    inverted_event = inverted_input in ("yes", "y")

    print("\nSelect Currency:")
    for i, cur in enumerate(CURRENCIES, 1):
        print(f"  {i}. {cur} ({', '.join(PAIR_SETS[cur][:3])}...)")
    currency_choice = int(input("\nChoice (1-8): ")) - 1
    event_currency = CURRENCIES[currency_choice]

    print("\nPaste Past Reactions (tab-separated with header):")
    print("Format: Date\tActual\tForecast\tHistory\tCurrency")
    print("(Enter empty line when done)\n")
    lines = []
    while True:
        line = input()
        if line.strip() == "" and lines:
            break
        lines.append(line)
    raw_data = "\n".join(lines)

    entry_hour = int(input("\nEntry time (hours after news): "))

    mode = "surprise" if "Payroll" in event_type or "CPI" in event_type or "FOMC" in event_type else "candle_colour"

    print(f"\nMode: {mode}")
    print(f"Event: {event_type}")
    print(f"Currency: {event_currency}")
    print(f"Pairs: {', '.join(PAIR_SETS[event_currency])}")
    print(f"Entry: {entry_hour}h after news")
    print(f"Inverted: {inverted_event}")
    print("-" * 60)

    news_df = parse_news_data(raw_data, event_currency, entry_hour, inverted_event, mode)
    if news_df.empty:
        print("No valid news data parsed. Check your input format.")
        return

    print(f"Parsed {len(news_df)} news events")

    pair_dfs = {}
    for pair in PAIR_SETS[event_currency]:
        try:
            from src.tools.price_data import load_csv
            pair_dfs[pair] = load_csv(pair)
        except FileNotFoundError:
            logger.warning(f"CSV not found for {pair}, skipping")

    if not pair_dfs:
        print("No price data CSVs found. Place CSV files in the project root.")
        return

    total_pasted = len(news_df)
    news_df = filter_by_price_data(news_df, pair_dfs)
    out_of_range = total_pasted - len(news_df)
    print(f"\nPasted data: {total_pasted}")
    print(f"Out of price data range: {out_of_range}")
    print(f"Fitting price data: {len(news_df)}")

    if mode == "surprise":
        news_df = filter_news_for_surprise(news_df)
        print(f"After surprise filter: {len(news_df)} events")
    elif mode == "candle_colour":
        news_df = filter_news_for_candle(news_df, pair_dfs)
        print(f"After candle filter: {len(news_df)} events")

    total_events = len(news_df)
    mid = total_events // 2
    train_news = news_df.iloc[:mid].reset_index(drop=True)
    fwd_news = news_df.iloc[mid:].reset_index(drop=True)

    print(f"\nTotal usable events: {total_events}")
    print(f"Train (first half): {len(train_news)} events")
    print(f"Forward Test (second half): {len(fwd_news)} events")

    print("\n--- Analyzing TRAIN ---")
    orchestrator_train = OrchestratorAgent(mode, event_currency, inverted_event, entry_hour)
    train_result = orchestrator_train.run(train_news)

    print("\n--- Analyzing FORWARD TEST ---")
    orchestrator_fwd = OrchestratorAgent(mode, event_currency, inverted_event, entry_hour)
    fwd_result = orchestrator_fwd.run(fwd_news)

    _print_summary(train_result, fwd_result, event_type, event_currency)
    _save_combined_excel(train_result, fwd_result, train_news, fwd_news, event_type, event_currency)


def _print_summary(train_result: dict, fwd_result: dict, event_type: str, currency: str):
    print("\n" + "=" * 60)
    print("  ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"Event: {event_type}")
    print(f"Currency: {currency}")
    print(f"Mode: {train_result['mode']}")

    for label, result in [("TRAIN", train_result), ("FORWARD TEST", fwd_result)]:
        agg = result["aggregation"]
        if "error" in agg:
            print(f"\n{label}: {agg['error']}")
            continue
        print(f"\n--- {label} Best Strategies ---")
        best = agg.get("best")
        if best is not None and not best.empty:
            for _, row in best.iterrows():
                pair = row.get("pair", "?")
                tp = row.get("tp_percent", 0)
                sl = row.get("sl_percent", 0)
                wr = row.get("win_rate_percent", 0)
                ev = row.get("beta_weighted_ev_R", 0)
                tc = row.get("trade_count", 0)
                sub = row.get("sub_mode", "")
                sub_str = f" [{sub}]" if sub != "N/A" else ""
                print(f"  {pair}{sub_str}: TP={tp:.1f}% SL={sl:.1f}% "
                      f"WR={wr:.1f}% EV={ev:.4f}R trades={tc}")

    print("\n" + "=" * 60)


def _save_combined_excel(train_result: dict, fwd_result: dict,
                         train_news, fwd_news, event_type: str, currency: str):
    from src.config import OUTPUT_DIR
    OUTPUT_DIR.mkdir(exist_ok=True)

    output_path = OUTPUT_DIR / f"{currency}_{event_type.replace(' ', '_').replace('(', '').replace(')', '')}.xlsx"

    train_best = train_result["aggregation"].get("best", pd.DataFrame())
    train_all = train_result["aggregation"].get("merged", pd.DataFrame())
    fwd_best = fwd_result["aggregation"].get("best", pd.DataFrame())
    fwd_all = fwd_result["aggregation"].get("merged", pd.DataFrame())

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        if not train_best.empty:
            train_best.to_excel(writer, sheet_name="Train_Best", index=False)
        if not train_all.empty:
            train_all.to_excel(writer, sheet_name="Train_All", index=False)
        if not fwd_best.empty:
            fwd_best.to_excel(writer, sheet_name="Fwd_Best", index=False)
        if not fwd_all.empty:
            fwd_all.to_excel(writer, sheet_name="Fwd_All", index=False)

        combined_best = pd.concat([train_best, fwd_best], ignore_index=True) if not train_best.empty and not fwd_best.empty else (train_best if not train_best.empty else fwd_best)
        if combined_best is not None and not combined_best.empty:
            combined_best.to_excel(writer, sheet_name="Combined_Best", index=False)

        if not train_news.empty:
            train_news.to_excel(writer, sheet_name="Train_News", index=False)
        if not fwd_news.empty:
            fwd_news.to_excel(writer, sheet_name="Fwd_News", index=False)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
