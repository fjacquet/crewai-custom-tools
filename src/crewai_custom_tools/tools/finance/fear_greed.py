"""CNN Fear & Greed Index Scraper Tool."""

import logging

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok

logger = logging.getLogger(__name__)


def score_to_sentiment(score: float) -> str:
    """Map Fear & Greed numeric score (0-100) to market classification."""
    if score <= 25:
        return "Extreme Fear"
    if score <= 45:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


class FearGreedInput(BaseModel):
    """Input schema for FearGreedTool (takes no arguments)."""


class FearGreedTool(BaseTool):
    """CNN Fear & Greed Index sentiment analysis tool."""

    name: str = "fear_and_greed_sentiment"
    description: str = "Fetches the current market-wide sentiment from the CNN Fear & Greed Index (0-100 and label)."
    args_schema: type[BaseModel] = FearGreedInput

    @api_tool(provider="CNN", endpoint="FearGreed")
    def _run(self) -> str:
        """Fetch Fear & Greed sentiment from CNN Dataviz endpoint."""
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        fear_greed_data = response.json().get("fear_and_greed", {})

        score = fear_greed_data.get("score")
        if score is None:
            return err("Failed to parse Fear & Greed score from API response")

        score_val = float(score)
        # CNN keys the historical points as previous_1_week/_month/_year.
        return ok(
            {
                "score": score_val,
                "sentiment": score_to_sentiment(score_val),
                "rating_label": fear_greed_data.get("rating"),
                "previous_close_score": fear_greed_data.get("previous_close"),
                "one_week_ago_score": fear_greed_data.get("previous_1_week"),
                "one_month_ago_score": fear_greed_data.get("previous_1_month"),
                "one_year_ago_score": fear_greed_data.get("previous_1_year"),
                "source": "CNN Fear & Greed",
            }
        )
