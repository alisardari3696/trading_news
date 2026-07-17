# Forex News Trading Backtester

Backtest forex trading strategies using economic calendar data from **Forex Factory** and historical price data from Yahoo Finance.

## How It Works

1. **Get price data** — Download 1-hour OHLC data for 7 currency pairs per group via `Gathering prices main.py` (uses Yahoo Finance)
2. **Get news data** — Copy-paste the Forex Factory calendar (History / Actual / Forecast / Previous columns) directly into the terminal
3. **Run the analysis** — Choose a currency group, entry time, and let the script grid-search over TP/SL combinations (0.002–0.011)
4. **Review results** — Exported to Excel with best parameters per pair, all results, and the news data used

## Trading Strategies

### Surprise (Event-Driven)
Trades based on the difference between Actual and Forecast values. If Actual > Forecast, it's a positive surprise; if Actual < Forecast, it's negative. Direction is determined by whether the pair starts or ends with the event currency.

### Candle Colour (Trend / Fade)
Trades based on the prior hour's candle colour:
- **Trend** mode — go long on green candles, short on red candles
- **Fade** mode — go short on green candles, long on red candles

## Output

Each run produces an `.xlsx` file in `results/` with three sheets:
- **Best_Per_Pair** — top TP/SL combo per pair by total PnL
- **All_Results** — every TP/SL combination ranked by performance
- **News_Used** — the calendar data that was pasted

## Version History

| Version | What Changed |
|---------|-------------|
| v1 | Baseline — Surprise and Candle Colour modes, file-based news loading, TP/SL grid search (0.1%-0.9%), 48h max hold, Excel output |
| v2 | Parse "k" and "m" suffixes in news Actual/Forecast values (e.g. "123k" → 123) |
| v3 | Handle date ranges in History column (e.g. "Jun 15-17"); mode-aware news loading (skips Actual/Forecast in Candle Colour mode) |
| v4 | Added semivariance metric (downside risk); All_Results sheet sorted by highest total PnL |
| v5 | Added risk-to-reward ratio (TP/SL) and average PnL of last 10 trades; Excel freeze panes on header rows |
| v6 | Replaced semivariance with coefficient of variation (std dev / mean) for normalized risk-adjusted metric |
| v7 | Performance optimization — NumPy pre-allocated arrays, C-engine CSV parsing, grid search restructured to cache valid entries |
| v8 | Added max drawdown metric (largest peak-to-trough decline in cumulative PnL) |
| v9 | Raised minimum TP/SL from 0.1% to 0.2% (dropped smallest grid points) |
| v10 | Clipboard paste replaces file-based news input; auto-mode detection; output to `results/` directory with dynamic filenames |
| v11 | Replaced 48-hour max hold with Friday 18:00 end-of-week cutoff; removed MAX_HOLD_HOURS constant |
| v12 | Restored manual mode selection; expanded TP/SL range to 1.1% (0.2%-1.1%) |
| v13 | Added positive/negative time ratio — tracks hours price was above vs below entry per trade, reports the mean ratio across all trades |

## Description Writer

The `description_writer.py` tool generates human-readable trading idea descriptions from the Excel output. Paste a row from `Best_Per_Pair`, choose an asset and direction, and it produces a formatted summary.

## Files

| File | Purpose |
|------|---------|
| `Gathering prices main.py` | Download 1h price data via Yahoo Finance |
| `Analyzing_v13.py` | Main backtest engine (latest version) |
| `description_writer.py` | Generate trading idea descriptions |
| `news.txt` | Sample Forex Factory calendar data |
| `*_1h.csv` | Price data files |
| `results/` | Output Excel files |
| `archive/` | Previous versions (v1–v12) |
