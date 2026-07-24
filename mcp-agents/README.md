# MCP Trading View Analyzer

Multi-Agent AI system for analyzing TradingView news-based charts across 8 currency pairs using Model Context Protocol.

## Architecture

```
User Input (Event Type, Currency, News Data)
        |
  [Orchestrator Agent]
   /        |        \
[Analysis] [Pair] [Pair]  ... x8 pairs
   \        |        /
  [Aggregator Agent]
        |
  Final Report (Excel + Summary)
```

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and edit environment variables
cp .env.example .env
# Edit .env with your API keys

# Validate configuration
python -m src.tools.validate

# Run the analyzer
python main.py
```

## Usage

```bash
python main.py
```

Follow the interactive prompts:
1. **Event Type** - NFP, CPI, FOMC, Interest Rate, Unemployment, GDP, Retail Sales, PMI, Inflation
2. **Inverted Event** - Yes/No (is higher actual worse for currency?)
3. **Currency** - USD, EUR, GBP, JPY, AUD, NZD, CHF, CAD
4. **Past Reactions** - Tab-separated data (Date, Actual, Forecast, History, Currency)
5. **Entry Time** - Time in hours (1-24) to enter after news

## Tools

| Tool | Description |
|------|-------------|
| `read_image` | Read and analyze TradingView chart images |
| `analyze_chart` | Find entry candle, color, price levels |
| `get_price_data` | Fetch OHLC data for currency pairs |
| `simulate_trade` | Run TP/SL grid search over reactions |
| `aggregate_results` | Merge results across all pairs |
| `create_excel` | Generate formatted Excel report |
| `search_news` | Find past reactions to similar events |

## Output

Results saved to `output/` directory as Excel files with:
- `Best_Strategies` - Top strategy per currency pair
- `All_Results` - Complete grid search results
- `Summary` - Aggregated view with win rates, confidence intervals

## File Structure

```
mcp-agents/
├── src/
│   ├── agents/          # Multi-agent framework
│   │   ├── orchestrator.py
│   │   ├── pair_analyzer.py
│   │   ├── aggregator.py
│   │   └── manager.py
│   ├── tools/           # Custom TradingView tools
│   │   ├── chart_reader.py
│   │   ├── price_data.py
│   │   ├── trade_simulator.py
│   │   ├── excel_writer.py
│   │   └── news_search.py
│   └── config.py
├── main.py
├── requirements.txt
├── .env.example
├── docs/
│   ├── ARCHITECTURE.md
│   ├── TOOLS.md
│   └── GUIDE.md
└── output/
```
