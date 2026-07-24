# Quickstart Guide

## Prerequisites

- Python 3.10+
- pip

## Step 1: Install

```bash
cd mcp-agents
pip install -r requirements.txt
```

## Step 2: Configure

```bash
cp .env.example .env
```

Edit `.env` with your API key:
```
OPENAI_API_KEY=sk-your-actual-key
```

## Step 3: Prepare Data

Place your TradingView CSV files in the project root:
```
EURUSD_1h.csv
GBPUSD_1h.csv
USDJPY_1h.csv
... (one for each pair)
```

CSV format:
```
Datetime,Open,High,Low,Close
2024-01-01 00:00:00,1.1000,1.1050,1.0950,1.1020
```

## Step 4: Run

```bash
python main.py
```

## Step 5: Follow Prompts

```
Select Event Type:
1. Non-Farm Payrolls (NFP)
2. Consumer Price Index (CPI)
...

> 1

Is higher actual worse for the currency? (yes/no):
> no

Select Currency:
1. USD  2. EUR  3. GBP  ...
> 1

Paste Past Reactions (tab-separated):
Date	Actual	Forecast	History	Currency
Jan 5, 2024	216000	175000	...	USD
...

(enter empty line when done)

Entry time (hours after news): 
> 0
```

## Output

Results saved to `output/` directory:
```
output/
└── USD_NFP_2024-01-05.xlsx
    ├── Best_Strategies
    ├── All_Results
    └── Summary
```

## Troubleshooting

### "No CSV files found"
- Ensure CSV files are in the project root
- File names must match pair names: `{PAIR}_1h.csv`

### "API key not found"
- Check `.env` file exists and has correct key
- Ensure `OPENAI_API_KEY` is set

### "Import error"
- Run `pip install -r requirements.txt`
- Ensure Python 3.10+

### Low win rates
- Check chart screenshot quality
- Verify event type and currency match
- Ensure past reactions are tab-separated correctly
