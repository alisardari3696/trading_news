import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats


def calculate_wilson_ci(wins: int, n: int, confidence: float = 0.95) -> tuple:
    if n == 0:
        return 0.0, 1.0
    p_hat = wins / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    spread = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return max(0, center - spread), min(1, center + spread)


def calculate_beta_ev(wins: int, losses: int, rr: float,
                      ci_low: float, ci_high: float, n_points: int = 500) -> float:
    a = wins + 0.5
    b = losses + 0.5
    x = np.linspace(ci_low, ci_high, n_points)
    pdf = stats.beta.pdf(x, a, b)
    pdf /= pdf.sum()
    ev_per_rate = x * rr - (1 - x)
    return float(np.sum(pdf * ev_per_rate))


def add_statistics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["ci_lower"] = 0.0
    df["ci_upper"] = 0.0
    df["beta_weighted_ev_R"] = 0.0

    for idx, row in df.iterrows():
        ci_low, ci_high = calculate_wilson_ci(int(row["wins"]), int(row["trade_count"]))
        beta_ev = calculate_beta_ev(
            int(row["wins"]), int(row["losses"]),
            row["risk_to_reward_ratio"], ci_low, ci_high,
        )
        df.at[idx, "ci_lower"] = round(ci_low * 100, 1)
        df.at[idx, "ci_upper"] = round(ci_high * 100, 1)
        df.at[idx, "beta_weighted_ev_R"] = round(beta_ev, 4)

    return df


def aggregate_results(pair_results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    all_dfs = []
    for pair, df in pair_results.items():
        if not df.empty:
            all_dfs.append(df)
    if not all_dfs:
        return pd.DataFrame()
    merged = pd.concat(all_dfs, ignore_index=True)
    merged = add_statistics(merged)
    merged = merged.sort_values("beta_weighted_ev_R", ascending=False)
    return merged


def get_best_per_pair(merged: pd.DataFrame, mode: str) -> pd.DataFrame:
    if merged.empty:
        return merged
    group_cols = ["pair", "sub_mode"] if mode == "candle_colour" else ["pair"]
    best = (
        merged.sort_values(group_cols + ["beta_weighted_ev_R"],
                           ascending=[True] * len(group_cols) + [False])
        .groupby(group_cols, as_index=False)
        .first()
    )
    return best
