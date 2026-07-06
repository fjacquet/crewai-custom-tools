"""Pydantic models for OSINTFR curated tools."""

from pydantic import BaseModel, Field
from typing import Optional


class EpieosLookupInput(BaseModel):
    """Input schema for EpieosEmailLookupTool."""
    email: str = Field(..., description="The target email address to reverse-search (e.g., 'test@gmail.com').")


class HoleheScanInput(BaseModel):
    """Input schema for HoleheEmailScannerTool."""
    email: str = Field(..., description="The target email address to scan across 150+ platforms.")


class OpenCorporatesSearchInput(BaseModel):
    """Input schema for OpenCorporatesSearchTool."""
    query: str = Field(..., description="The name of the company or registration ID to search for globally.")
    jurisdiction_code: Optional[str] = Field(None, description="Optional: 2-letter country or state code (e.g., 'us_ca', 'gb') to restrict search.")
