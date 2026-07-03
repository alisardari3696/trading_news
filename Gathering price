import yfinance as yf
import pandas as pd

# 7 pairs for each asset
pair_sets = {
    "USD": {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "AUDUSD": "AUDUSD=X",
        "NZDUSD": "NZDUSD=X",
        "USDCAD": "USDCAD=X",
        "USDCHF": "USDCHF=X"
    },
    "EUR": {
        "EURUSD": "EURUSD=X",
        "EURJPY": "EURJPY=X",
        "EURGBP": "EURGBP=X",
        "EURAUD": "EURAUD=X",
        "EURNZD": "EURNZD=X",
        "EURCHF": "EURCHF=X",
        "EURCAD": "EURCAD=X"
    },
    "GBP": {
        "GBPUSD": "GBPUSD=X",
        "GBPJPY": "GBPJPY=X",
        "EURGBP": "EURGBP=X",
        "GBPAUD": "GBPAUD=X",
        "GBPNZD": "GBPNZD=X",
        "GBPCHF": "GBPCHF=X",
        "GBPCAD": "GBPCAD=X"
    },
    "JPY": {
        "USDJPY": "USDJPY=X",
        "EURJPY": "EURJPY=X",
        "GBPJPY": "GBPJPY=X",
        "AUDJPY": "AUDJPY=X",
        "NZDJPY": "NZDJPY=X",
        "CADJPY": "CADJPY=X",
        "CHFJPY": "CHFJPY=X"
    },
    "AUD": {
        "AUDUSD": "AUDUSD=X",
        "AUDJPY": "AUDJPY=X",
        "EURAUD": "EURAUD=X",
        "GBPAUD": "GBPAUD=X",
        "AUDNZD": "AUDNZD=X",
        "AUDCHF": "AUDCHF=X",
        "AUDCAD": "AUDCAD=X"
    },
    "NZD": {
        "NZDUSD": "NZDUSD=X",
        "NZDJPY": "NZDJPY=X",
        "EURNZD": "EURNZD=X",
        "GBPNZD": "GBPNZD=X",
        "AUDNZD": "AUDNZD=X",
        "NZDCHF": "NZDCHF=X",
        "NZDCAD": "NZDCAD=X"
    },
    "CHF": {
        "USDCHF": "USDCHF=X",
        "EURCHF": "EURCHF=X",
        "GBPCHF": "GBPCHF=X",
        "AUDCHF": "AUDCHF=X",
        "NZDCHF": "NZDCHF=X",
        "CADCHF": "CADCHF=X",
        "CHFJPY": "CHFJPY=X"
    },
    "CAD": {
        "USDCAD": "USDCAD=X",
        "EURCAD": "EURCAD=X",
        "GBPCAD": "GBPCAD=X",
        "AUDCAD": "AUDCAD=X",
        "NZDCAD": "NZDCAD=X",
        "CADJPY": "CADJPY=X",
        "CADCHF": "CADCHF=X"
    }
}

# ask user
news_currency = input(
    "Which news currency do you want data for? "
    "(USD, EUR, GBP, JPY, AUD, NZD, CHF, CAD): "
).strip().upper()

if news_currency not in pair_sets:
    print("Invalid currency entered.")
else:
    pairs = pair_sets[news_currency]
    print(f"\nDownloading 1H data for {news_currency} pairs...\n")

    for name, ticker in pairs.items():
        print(f"Downloading {name} ...")

        try:
            df = yf.download(
                ticker,
                interval="1h",
                period="730d"
            )

            if df.empty:
                print(f"No data found for {name}")
                continue

            df = df.reset_index()
            df.to_csv(f"{name}_1h.csv", index=False)

            print(f"{name} saved successfully.")

        except Exception as e:
            print(f"Error downloading {name}: {e}")

    print("\nDone.")
