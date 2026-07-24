import pandas as pd
import logging
from src.agents.base import Agent, AgentMessage, AgentResult
from src.tools.price_data import load_csv, grid_search

logger = logging.getLogger(__name__)


class PairAnalyzerAgent(Agent):
    def __init__(self, pair: str, mode: str, event_currency: str,
                 inverted_event: bool, entry_hour: int):
        super().__init__(agent_id=f"analyzer_{pair}", agent_type="pair_analyzer")
        self.pair = pair
        self.mode = mode
        self.event_currency = event_currency
        self.inverted_event = inverted_event
        self.entry_hour = entry_hour

    def analyze(self, news_df: pd.DataFrame, data_dir=None) -> AgentResult:
        try:
            if data_dir:
                df = load_csv(self.pair, data_dir)
            else:
                df = load_csv(self.pair)

            results = grid_search(
                pair=self.pair,
                df=df,
                mode=self.mode,
                event_currency=self.event_currency,
                news_df=news_df,
            )

            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                status="success",
                data={"pair": self.pair, "results": results, "row_count": len(results)},
            )
        except Exception as e:
            logger.error(f"Error analyzing {self.pair}: {e}")
            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                status="error",
                data={"pair": self.pair, "results": pd.DataFrame()},
                error=str(e),
            )
