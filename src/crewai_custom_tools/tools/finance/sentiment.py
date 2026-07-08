"""Sentiment analysis tools (VADER-based) for finance/news text."""

from functools import lru_cache
from typing import Any, Dict, List, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from crewai_custom_tools.core.results import err, ok

# VADER's standard compound thresholds.
_BULLISH = 0.05
_BEARISH = -0.05


@lru_cache(maxsize=1)
def _analyzer() -> SentimentIntensityAnalyzer:
    """Cache the (stateless) analyzer so its lexicon loads once."""
    return SentimentIntensityAnalyzer()


def _label(compound: float) -> str:
    """Map a compound score (-1..1) to a market label via transparent thresholds."""
    if compound >= _BULLISH:
        return "Bullish"
    if compound <= _BEARISH:
        return "Bearish"
    return "Neutral"


def score_texts(texts: List[str]) -> Dict[str, Any]:
    """Score a list of texts and aggregate — the shared engine for both tools.

    Returns per-text compound scores, the mean compound, a 0-100 normalized score
    ((compound + 1) / 2 * 100), and a Bearish/Neutral/Bullish label.
    """
    analyzer = _analyzer()
    per_text = [
        {"text": t, "compound": analyzer.polarity_scores(t)["compound"]}
        for t in texts
        if t and t.strip()
    ]
    if not per_text:
        return {"count": 0, "compound": 0.0, "score_0_100": 50.0, "label": "Neutral"}

    compound = sum(item["compound"] for item in per_text) / len(per_text)
    return {
        "count": len(per_text),
        "compound": round(compound, 4),
        "score_0_100": round((compound + 1) / 2 * 100, 1),
        "label": _label(compound),
        "per_text": per_text,
    }


class SentimentAnalysisInput(BaseModel):
    """Input schema for StandardizedSentimentAnalysisTool."""

    text: Optional[str] = Field(
        default=None, description="A single text/headline to score."
    )
    texts: Optional[List[str]] = Field(
        default=None,
        description="A list of texts/headlines to score and aggregate (use instead of `text`).",
    )


class StandardizedSentimentAnalysisTool(BaseTool):
    """Score finance/news text sentiment with VADER into a standardized 0-100 score."""

    name: str = "standardized_sentiment_analysis"
    description: str = (
        "Analyze the sentiment of finance/news text using VADER. Returns per-text "
        "compound scores, an aggregate compound (-1..1), a normalized 0-100 score, and "
        "a Bearish/Neutral/Bullish label. Provide `text` or a list of `texts`."
    )
    args_schema: type[BaseModel] = SentimentAnalysisInput

    def _run(self, text: Optional[str] = None, texts: Optional[List[str]] = None) -> str:
        """Score one text or a list of texts."""
        items = texts if texts else ([text] if text else [])
        if not any(t and t.strip() for t in items):
            return err("Provide non-empty `text` or `texts` to analyze.")
        return ok(score_texts(items))


class CrossAssetSentimentInput(BaseModel):
    """Input schema for CrossAssetSentimentComparatorTool."""

    assets: Dict[str, List[str]] = Field(
        ...,
        description="Mapping of asset/ticker name -> its list of texts/headlines to score.",
    )


class CrossAssetSentimentComparatorTool(BaseTool):
    """Compare and rank sentiment across multiple assets using the same VADER engine."""

    name: str = "cross_asset_sentiment_comparator"
    description: str = (
        "Compare sentiment across assets. Provide `assets` as a mapping of asset name "
        "to its list of texts; returns each asset's score/label, a most→least bullish "
        "ranking, and the most bullish/bearish asset."
    )
    args_schema: type[BaseModel] = CrossAssetSentimentInput

    def _run(self, assets: Dict[str, List[str]]) -> str:
        """Score each asset and rank most→least bullish."""
        scored = {
            name: score_texts(texts)
            for name, texts in (assets or {}).items()
            if any(t and t.strip() for t in (texts or []))
        }
        if not scored:
            return err("Provide `assets` mapping each name to a non-empty list of texts.")

        comparison = {
            name: {"score_0_100": s["score_0_100"], "compound": s["compound"], "label": s["label"]}
            for name, s in scored.items()
        }
        ranking = sorted(comparison, key=lambda n: comparison[n]["compound"], reverse=True)
        return ok(
            {
                "comparison": comparison,
                "ranking": ranking,
                "most_bullish": ranking[0],
                "most_bearish": ranking[-1],
            }
        )
