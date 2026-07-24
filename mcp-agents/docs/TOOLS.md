# MCP Trading Analyzer - Tools Reference

## Chart Tools

### `read_image(path: str) -> str`
Reads and describes a TradingView chart image.
- **Input**: Path to PNG/JPG file
- **Output**: Description of chart elements (candles, indicators, patterns)
- **LLM**: Uses multimodal model to interpret chart

### `analyze_chart(description: str, event_time: str, entry_hour: int, inverted: bool, news_count: int) -> dict`
Analyzes chart description to find trading signals.
- **Input**: Chart description, event parameters
- **Output**: 
  - `entry_candle`: dict with index, time, open, high, low, close, color, direction
  - `num_reaction_candles`: count of reaction candles

## Price Data Tools

### `get_price_data(pair: str, timeframe: str, start: str, end: str) -> pd.DataFrame`
Fetches OHLC price data from CSV files.
- **Input**: Currency pair, timeframe, date range
- **Output**: DataFrame with Datetime, Open, High, Low, Close
- **CSV Format**: `{pair}_{timeframe}.csv` with skiprows=[1]

### `find_entry_candle(df: pd.DataFrame, event_time: str, entry_hour: int) -> dict`
Finds the candle closest to event release time.
- **Input**: OHLC DataFrame, event time, entry hour offset
- **Output**: Candle details (time, OHLC, color, index)

## Trading Tools

### `simulate_trade(df, entry, direction, tp, sl, same_candle_rule) -> dict`
Simulates a single trade with given parameters.
- **Input**: OHLC data, entry details, TP/SL percentages
- **Output**: PnL, hold time, exit reason, positive/negative hours

### `grid_search(pair, df, mode, event_currency, news_df, sub_mode, tp_values, sl_values) -> pd.DataFrame`
Runs TP/SL grid search across past reactions.
- **Input**: Pair, OHLC data, mode, reactions, parameter ranges
- **Output**: DataFrame with results for each (TP, SL) combination
- **Modes**: "surprise" or "candle_colour"
- **Sub-modes**: "trend" or "fade" (for candle_colour mode)

## Aggregation Tools

### `aggregate_results(pair_results: dict) -> pd.DataFrame`
Merges results across multiple currency pairs.
- **Input**: Dict of pair → results DataFrame
- **Output**: Merged DataFrame with all pairs

### `add_confidence_intervals(df: pd.DataFrame) -> pd.DataFrame`
Adds Wilson score confidence intervals.
- **Input**: Results DataFrame
- **Output**: DataFrame with ci_lower, ci_upper columns

### `add_beta_weighted_ev(df: pd.DataFrame) -> pd.DataFrame`
Calculates Bayesian expected value.
- **Input**: Results DataFrame with wins, losses
- **Output**: DataFrame with beta_weighted_ev column

## Output Tools

### `create_excel(results_df, best_df, output_path) -> str`
Creates formatted Excel report.
- **Input**: Full results, best strategies, output path
- **Output**: Path to created Excel file
- **Sheets**: Best_Strategies, All_Results, Summary

### `save_screenshot(page, pair, event, currency) -> str`
Captures TradingView chart screenshot.
- **Input**: Playwright page, pair, event, currency
- **Output**: Path to saved PNG

## News Tools

### `search_news(event_type: str, currency: str) -> pd.DataFrame`
Searches for past news reactions.
- **Input**: Event type, currency
- **Output**: DataFrame with past reactions (Date, Actual, Forecast, History, Currency)

## Utility Tools

### `calculate_wilson_ci(wins, n, confidence) -> tuple`
Calculates Wilson score confidence interval.
- **Input**: Win count, total trades, confidence level
- **Output**: (lower_bound, upper_bound)

### `calculate_beta_ev(wins, losses, rr, ci_low, ci_high) -> float`
Calculates beta-weighted expected value.
- **Input**: Win/loss counts, risk/reward ratio, CI bounds
- **Output**: Expected value in R-multiples

## Tool Registration

Tools are registered as MCP resources:

```python
@mcp.resource("trading://tools/{tool_name}")
def get_tool(tool_name: str):
    return tools.get(tool_name)
```

## Tool Dependencies

| Tool | Dependencies |
|------|-------------|
| read_image | Pillow |
| analyze_chart | (uses LLM) |
| get_price_data | pandas, pathlib |
| simulate_trade | numpy |
| grid_search | pandas, numpy |
| aggregate_results | pandas |
| create_excel | openpyxl |
| search_news | pandas |
