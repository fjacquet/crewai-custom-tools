"""Wikipedia content processing — key facts and query/section summaries.

Reuses ``WikipediaArticleTool`` (MediaWiki API) to fetch content, so it needs no extra
``wikipedia`` library dependency.
"""

import json
from enum import StrEnum
from typing import Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.tools.web.wikipedia import ArticleAction, WikipediaArticleTool


class ProcessingAction(StrEnum):
    """Processing actions on a fetched Wikipedia article."""

    EXTRACT_KEY_FACTS = "extract_key_facts"
    SUMMARIZE_FOR_QUERY = "summarize_article_for_query"
    SUMMARIZE_SECTION = "summarize_article_section"


class WikipediaProcessingToolInput(BaseModel):
    """Input schema for WikipediaProcessingTool."""

    title: str = Field(..., description="The title of the Wikipedia article.")
    action: ProcessingAction = Field(..., description="The processing action to perform.")
    query: Optional[str] = Field(None, description="Query to tailor the summary for (query action).")
    section_title: Optional[str] = Field(None, description="Section to summarize (section action).")
    max_length: int = Field(150, description="Maximum length of the returned summary.")
    count: int = Field(5, description="Number of key-fact sentences to extract.")


def _fetch(title: str, action: ArticleAction) -> tuple[Optional[dict], Optional[str]]:
    """Fetch article data via WikipediaArticleTool; return (data, error_message)."""
    payload: dict[str, Any] = json.loads(WikipediaArticleTool()._run(title=title, action=action))
    if not payload["success"]:
        return None, payload["error"]
    return payload["data"], None


def _truncate(text: str, max_length: int) -> str:
    """Truncate text to max_length, appending an ellipsis when clipped."""
    return text[:max_length] + ("..." if len(text) > max_length else "")


class WikipediaProcessingTool(BaseTool):
    """Process a Wikipedia article: extract key facts or produce a tailored summary."""

    name: str = "wikipedia_article_processor"
    description: str = (
        "Process a Wikipedia article — extract key facts, or produce a summary tailored to a "
        "query or a specific section."
    )
    args_schema: type[BaseModel] = WikipediaProcessingToolInput

    def _run(
        self,
        title: str,
        action: str,
        query: Optional[str] = None,
        section_title: Optional[str] = None,
        max_length: int = 150,
        count: int = 5,
    ) -> str:
        """Fetch the article via WikipediaArticleTool and apply the requested processing."""
        if action == ProcessingAction.EXTRACT_KEY_FACTS:
            data, error = _fetch(title, ArticleAction.GET_SUMMARY)
            if error:
                return err(error)
            sentences = [s.strip() for s in data.get("summary", "").replace("\n", " ").split(". ") if s.strip()]
            facts = ". ".join(sentences[:count])
            if facts and not facts.endswith("."):
                facts += "."
            return ok({"title": title, "key_facts": facts})

        if action == ProcessingAction.SUMMARIZE_FOR_QUERY:
            if not query:
                return err("'query' is required for summarize_article_for_query")
            data, error = _fetch(title, ArticleAction.GET_ARTICLE)
            if error:
                return err(error)
            paragraphs = [p for p in data.get("content", "").split("\n") if query.lower() in p.lower()]
            if not paragraphs:
                summary_data, summary_err = _fetch(title, ArticleAction.GET_SUMMARY)
                fallback = "" if summary_err else summary_data.get("summary", "")
                return ok({"title": title, "query": query, "matched": False, "summary": fallback})
            return ok(
                {
                    "title": title,
                    "query": query,
                    "matched": True,
                    "summary": _truncate("\n".join(paragraphs), max_length),
                }
            )

        if action == ProcessingAction.SUMMARIZE_SECTION:
            if not section_title:
                return err("'section_title' is required for summarize_article_section")
            data, error = _fetch(title, ArticleAction.GET_ARTICLE)
            if error:
                return err(error)
            content = data.get("content", "")
            idx = content.lower().find(section_title.lower())
            if idx == -1:
                return err(f"Section '{section_title}' not found in '{title}'")
            return ok(
                {
                    "title": title,
                    "section": section_title,
                    "summary": _truncate(content[idx : idx + max_length + len(section_title)], max_length),
                }
            )

        return err(f"Unknown action '{action}'")
