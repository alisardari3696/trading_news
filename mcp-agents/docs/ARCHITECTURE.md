# MCP Trading Analyzer - Architecture

## Multi-Agent System

### Agent Hierarchy

```
OrchestratorAgent
├── Decomposes user input into per-pair analysis tasks
├── Creates AnalyzingAgent for each of 8 currency pairs
├── Manages parallel execution
└── Passes results to AggregatorAgent

AnalyzingAgent (x8)
├── Receives: pair, event_type, news_data, past_reactions
├── Reads TradingView chart image
├── Finds entry candle and its color
├── Fetches OHLC price data from CSV
├── Runs TP/SL grid search across past reactions
└── Returns: results DataFrame + summary stats

AggregatorAgent
├── Receives results from all AnalyzingAgents
├── Merges by currency pair
├── Adds confidence intervals (Wilson score)
├── Calculates beta-weighted expected values
├── Ranks strategies
└── Generates Excel output
```

### Agent Communication

Agents communicate via typed messages:

```python
AgentMessage(
    sender="pair_analyzer",
    receiver="aggregator", 
    message_type="result",
    payload={"pair": "EURUSD", "results": df, "summary": dict}
)
```

### Agent States

```
IDLE → THINKING → EXECUTING → REPORTING → IDLE
```

## Tools

### MCP Tool Specification

Each tool follows the MCP pattern:

```python
@mcp.tool()
async def tool_name(param: type) -> result_type:
    """Tool description for LLM"""
    # Implementation
```

### Tool Registry

Tools are registered in `config.py`:

```python
tools = {
    "read_image": read_image,
    "analyze_chart": analyze_chart,
    "get_price_data": get_price_data,
    "simulate_trade": simulate_trade,
    "aggregate_results": aggregate_results,
    "create_excel": create_excel,
    "search_news": search_news,
}
```

## Data Flow

### 1. Input Phase
- User provides: event type, currency, past reactions, entry time
- Orchestrator validates and structures input
- Creates analysis tasks for each pair

### 2. Analysis Phase
- Each AnalyzingAgent processes one pair in parallel:
  1. Read TradingView chart → find entry candle
  2. Fetch OHLC data from CSV
  3. Run grid search (8x8 TP/SL = 64 strategies)
  4. Calculate statistics per strategy

### 3. Aggregation Phase
- Combine results from all pairs
- Calculate cross-pair metrics
- Rank by beta-weighted EV
- Generate Excel report

### 4. Output Phase
- Excel file with multiple sheets
- Console summary of best strategies

## Performance Considerations

- **Parallel Execution**: All 8 pairs analyzed concurrently
- **Caching**: Price data cached per session
- **Batch Operations**: Grid search optimized with numpy
- **Incremental Results**: Results streamed as available

## Error Handling

- Missing CSV: Skip pair, report warning
- Invalid chart: Fallback to manual candle detection
- API failure: Retry with exponential backoff
- No valid trades: Report empty results for pair

## Extension Points

- Add new tools via `@mcp.tool()` decorator
- Add new agents by extending `Agent` base class
- Add new analysis modes in `OrchestratorAgent`
- Add new output formats in `AggregatorAgent`
