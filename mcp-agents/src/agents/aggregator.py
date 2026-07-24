import pandas as pd
import logging
from pathlib import Path
from src.agents.base import Agent, AgentResult
from src.tools.aggregator import aggregate_results, get_best_per_pair
from src.tools.excel_writer import create_excel

logger = logging.getLogger(__name__)


class AggregatorAgent(Agent):
    def __init__(self, mode: str, output_dir: Path = None):
        super().__init__(agent_id="aggregator", agent_type="aggregator")
        self.mode = mode
        self.output_dir = output_dir

    def aggregate(self, pair_results: dict[str, AgentResult]) -> dict:
        pair_dfs = {}
        for pair, result in pair_results.items():
            if result.status == "success" and not result.data["results"].empty:
                pair_dfs[pair] = result.data["results"]

        if not pair_dfs:
            return {"error": "No valid results to aggregate"}

        merged = aggregate_results(pair_dfs)
        best = get_best_per_pair(merged, self.mode)

        output_path = create_excel(merged, best, self.output_dir)
        logger.info(f"Excel saved to: {output_path}")

        return {
            "merged": merged,
            "best": best,
            "output_path": str(output_path),
            "total_strategies": len(merged),
            "pairs_analyzed": len(pair_dfs),
        }
