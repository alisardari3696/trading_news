import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from src.agents.base import Agent, AgentMessage, AgentResult
from src.agents.pair_analyzer import PairAnalyzerAgent
from src.agents.aggregator import AggregatorAgent
from src.config import PAIR_SETS, CSV_DIR, OUTPUT_DIR

logger = logging.getLogger(__name__)


class OrchestratorAgent(Agent):
    def __init__(self, mode: str, event_currency: str, inverted_event: bool, entry_hour: int):
        super().__init__(agent_id="orchestrator", agent_type="orchestrator")
        self.mode = mode
        self.event_currency = event_currency
        self.inverted_event = inverted_event
        self.entry_hour = entry_hour
        self.pairs = PAIR_SETS.get(event_currency, [])

    def run(self, news_df) -> dict:
        pair_analyzers = {}
        for pair in self.pairs:
            analyzer = PairAnalyzerAgent(
                pair=pair,
                mode=self.mode,
                event_currency=self.event_currency,
                inverted_event=self.inverted_event,
                entry_hour=self.entry_hour,
            )
            pair_analyzers[pair] = analyzer

        pair_results = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {}
            for pair, analyzer in pair_analyzers.items():
                future = executor.submit(analyzer.analyze, news_df, CSV_DIR)
                futures[future] = pair

            for future in futures:
                pair = futures[future]
                try:
                    result = future.result()
                    pair_results[pair] = result
                    status = "OK" if result.status == "success" else f"ERR: {result.error}"
                    logger.info(f"{pair}: {status} ({result.data.get('row_count', 0)} rows)")
                except Exception as e:
                    logger.error(f"{pair} failed: {e}")
                    pair_results[pair] = AgentResult(
                        agent_id=f"analyzer_{pair}",
                        agent_type="pair_analyzer",
                        status="error",
                        data={"pair": pair, "results": __import__('pandas').DataFrame()},
                        error=str(e),
                    )

        aggregator = AggregatorAgent(mode=self.mode, output_dir=OUTPUT_DIR)
        agg_result = aggregator.aggregate(pair_results)

        return {
            "mode": self.mode,
            "currency": self.event_currency,
            "inverted_event": self.inverted_event,
            "entry_hour": self.entry_hour,
            "pair_results": pair_results,
            "aggregation": agg_result,
        }
