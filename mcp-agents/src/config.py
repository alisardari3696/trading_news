from pathlib import Path

DATA_DIR = Path(".")
OUTPUT_DIR = DATA_DIR / "output"
CSV_DIR = DATA_DIR

PAIR_SETS = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"],
    "EUR": ["EURUSD", "EURJPY", "EURGBP", "EURAUD", "EURNZD", "EURCHF", "EURCAD"],
    "GBP": ["GBPUSD", "GBPJPY", "EURGBP", "GBPAUD", "GBPNZD", "GBPCHF", "GBPCAD"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY"],
    "AUD": ["AUDUSD", "AUDJPY", "EURAUD", "GBPAUD", "AUDNZD", "AUDCHF", "AUDCAD"],
    "NZD": ["NZDUSD", "NZDJPY", "EURNZD", "GBPNZD", "AUDNZD", "NZDCHF", "NZDCAD"],
    "CHF": ["USDCHF", "EURCHF", "GBPCHF", "AUDCHF", "NZDCHF", "CADCHF", "CHFJPY"],
    "CAD": ["USDCAD", "EURCAD", "GBPCAD", "AUDCAD", "NZDCAD", "CADCHF", "CADJPY"],
}

EVENT_TYPES = [
    "Non-Farm Payrolls (NFP)",
    "Consumer Price Index (CPI)",
    "Federal Open Market Committee (FOMC)",
    "Interest Rate Decision",
    "Unemployment Rate",
    "Gross Domestic Product (GDP)",
    "Retail Sales",
    "Purchasing Managers Index (PMI)",
    "Inflation Rate",
]

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CHF", "CAD"]

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
