import numpy as np
import pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
from scipy import stats
import re

DATA_DIR = Path(".")
OUTPUT_DIR = DATA_DIR / "results"

TP_VALUES = [x / 1000 for x in range(2, 10)]
SL_VALUES = [x / 1000 for x in range(2, 10)]

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


def wilson_ci(wins, n, confidence=0.95):
    if n == 0:
        return 0.0, 1.0
    p_hat = wins / n
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    spread = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return max(0, center - spread), min(1, center + spread)


def beta_weighted_ev(wins, losses, rr, ci_low, ci_high, n_points=500):
    a = wins + 0.5
    b = losses + 0.5
    x = np.linspace(ci_low, ci_high, n_points)
    pdf = stats.beta.pdf(x, a, b)
    pdf /= pdf.sum()
    ev_per_rate = x * rr - (1 - x)
    return float(np.sum(pdf * ev_per_rate))

# ... archived historical content preserved
