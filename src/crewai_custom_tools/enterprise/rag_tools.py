"""RAG Vector database search and persistence tools."""

import logging

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

    @api_tool(provider="RAG", endpoint="StoreText")
    def _run(self, text: str) -> str:
        """Add a text block to the local vector database.

        Any failure (missing backend, import error, add() error) propagates to
        @api_tool and becomes an error envelope — we never report a fake success (H8).
        """
        from crewai_tools import RagTool

        RagTool().add(text, data_type="text")
        return ok({"stored": True, "preview": text[:100]})
