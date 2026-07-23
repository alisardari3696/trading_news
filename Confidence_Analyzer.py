import numpy as np
from scipy import stats
from io import StringIO

try:
    import pandas as pd
except ImportError:
    print("Install pandas: pip install pandas")
    exit(1)


def paste_rows():
    print("\nPaste your v13 results below (with header row, tab-separated).")
    print("Enter an empty line when done:\n")
    lines = []
    while True:
        line = input()
        if line.strip() == "" and lines:
            break
        lines.append(line)
    if not lines:
        print("No data pasted.")
        return None
    raw = "\n".join(lines)
    return pd.read_csv(StringIO(raw), sep="\t")


def wilson_ci(wins, n, confidence=0.95):
    if n == 0:
        return 0.0, 1.0
    p_hat = wins / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    spread = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return max(0, center - spread), min(1, center + spread)


def beta_weighted_ev(wins, losses, rr, ci_low, ci_high, n_points=1000):
    a = wins + 0.5
    b = losses + 0.5
    x = np.linspace(ci_low, ci_high, n_points)
    pdf = stats.beta.pdf(x, a, b)
    pdf /= pdf.sum()

    ev_per_rate = x * rr - (1 - x)
    weighted_ev = np.sum(pdf * ev_per_rate)

    best_idx = np.argmax(pdf)
    best_rate = x[best_idx]

    ev_if_best = best_rate * rr - (1 - best_rate)

    return {
        "weighted_ev": weighted_ev,
        "best_ev": ev_if_best,
        "best_rate_at_peak": best_rate,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "x": x,
        "pdf": pdf,
        "ev_curve": ev_per_rate,
    }


def analyze_row(row):
    n = int(row.get("trade_count", 0))
    if n == 0:
        return None

    wr = row.get("win_rate_percent", 0) / 100
    rr = row.get("risk_to_reward_ratio", 1.0)
    wins = int(round(wr * n))
    losses = n - wins

    ci_low, ci_high = wilson_ci(wins, n)

    result = beta_weighted_ev(wins, losses, rr, ci_low, ci_high)
    result["trade_count"] = n
    result["raw_win_rate"] = wr
    result["rr"] = rr
    result["pair"] = row.get("pair", "N/A")
    result["tp_pct"] = row.get("tp_percent", "N/A")
    result["sl_pct"] = row.get("sl_percent", "N/A")
    result["wins"] = wins
    result["losses"] = losses

    return result


def print_result(r, idx):
    if r is None:
        return
    ev = r["weighted_ev"]
    verdict = "PROFITABLE" if ev > 0 else "NOT PROFITABLE"

    print(f"\n{'='*60}")
    print(f"  ROW {idx}: {r['pair']}  TP={r['tp_pct']}%  SL={r['sl_pct']}%")
    print(f"{'='*60}")
    print(f"  Trades: {r['trade_count']}  (Wins: {r['wins']}, Losses: {r['losses']})")
    print(f"  Raw Win Rate: {r['raw_win_rate']*100:.1f}%")
    print(f"  Risk:Reward:  1:{r['rr']:.2f}")
    print(f"  95% CI:       [{r['ci_low']*100:.1f}% , {r['ci_high']*100:.1f}%]")
    print(f"  ---")
    print(f"  Beta-Weighted Avg EV:  {ev:+.4f}R per trade  =>  {verdict}")
    print(f"  EV at peak density:    {r['best_ev']:+.4f}R  (at {r['best_rate_at_peak']*100:.1f}% WR)")
    print(f"  EV at raw WR:          {(r['raw_win_rate']*r['rr'] - (1-r['raw_win_rate'])):+.4f}R")

    if r["ci_low"] > 0.5:
        print(f"  >> CI floor > 50% with RR={r['rr']:.2f} => VERY STRONG signal")
    elif ev > 0 and r["ci_low"] > (1 / (1 + r["rr"])):
        print(f"  >> Even worst-case WR in CI is above breakeven => ROBUST")
    elif ev > 0:
        print(f"  >> Avg is positive but CI includes sub-breakeven => MARGINAL")
    else:
        print(f"  >> Average EV is negative => AVOID")


def main():
    df = paste_rows()
    if df is None:
        return

    required = ["trade_count", "win_rate_percent"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Missing columns: {missing}")
        print(f"Available: {list(df.columns)}")
        return

    if "risk_to_reward_ratio" not in df.columns:
        if "tp_percent" in df.columns and "sl_percent" in df.columns:
            df["risk_to_reward_ratio"] = df["tp_percent"] / df["sl_percent"]
        else:
            print("Need risk_to_reward_ratio or both tp_percent + sl_percent")
            return

    print(f"\nAnalyzing {len(df)} rows...\n")

    results = []
    for i, (_, row) in enumerate(df.iterrows()):
        r = analyze_row(row)
        results.append(r)
        print_result(r, i + 1)

    valid = [r for r in results if r is not None]
    if not valid:
        print("\nNo valid rows to analyze.")
        return

    avg_ev = np.mean([r["weighted_ev"] for r in valid])
    print(f"\n{'='*60}")
    print(f"  SUMMARY ACROSS ALL {len(valid)} ROWS")
    print(f"{'='*60}")
    print(f"  Avg Beta-Weighted EV: {avg_ev:+.4f}R per trade")
    profitable = sum(1 for r in valid if r["weighted_ev"] > 0)
    print(f"  Profitable rows: {profitable}/{len(valid)}")
    if avg_ev > 0:
        print(f"  => Strategy looks PROFITABLE on average")
    else:
        print(f"  => Strategy looks NOT PROFITABLE on average")


if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
