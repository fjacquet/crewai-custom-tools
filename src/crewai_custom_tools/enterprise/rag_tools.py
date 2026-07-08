"""RAG Vector database search and persistence tools."""

import logging
from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import ok

logger = logging.getLogger(__name__)


class SaveToRagInput(BaseModel):
    """Input schema for SaveToRagTool."""

    text: str = Field(
        ...,
        description="The arbitrary text chunk to store in the project knowledge base RAG vector database.",
    )


class SaveToRagTool(BaseTool):
    """A tool to store research, snippets, or reports directly in a local vector database."""

    name: str = "save_to_rag"
    description: str = "Persist arbitrary text chunks so they can be retrieved and searched later via RAG query tools."
    args_schema: type[BaseModel] = SaveToRagInput
    # Optional pre-configured crewai_tools.RagTool supplied by the caller (see __init__).
    rag_tool: Any = None

    def __init__(self, rag_tool: Any = None, **kwargs: Any) -> None:
        """Accept an optional pre-configured ``RagTool`` bound to the caller's collection.

        The caller (e.g. epic_news's ``get_rag_tools``) supplies a ``RagTool`` wired to the
        correct chromadb collection/embeddings; without it we fall back to a bare default
        ``RagTool()`` at call time. We keep the value on the private ``_rag_tool`` attribute
        so it is never subject to pydantic field validation.
        """
        super().__init__(**kwargs)
        self._rag_tool = rag_tool

    @api_tool(provider="RAG", endpoint="StoreText")
    def _run(self, text: str) -> str:
        """Add a text block to the injected (or default) local vector database.

        Any failure (missing backend, import error, add() error) propagates to
        @api_tool and becomes an error envelope — we never report a fake success (H8).
        """
        rag_tool = self._rag_tool
        if rag_tool is None:
            from crewai_tools import RagTool

            rag_tool = RagTool()
        rag_tool.add(text, data_type="text")
        return ok({"stored": True, "preview": text[:100]})
