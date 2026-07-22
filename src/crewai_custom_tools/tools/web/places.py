"""Geoapify Places API tool for points-of-interest search."""

import os
from typing import Any, Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok


class GeoapifyPlacesInput(BaseModel):
    """Input schema for Geoapify Places search."""

    categories: list[str] | None = Field(
        None, description="Category IDs, e.g. ['catering.restaurant', 'commercial.supermarket']."
    )
    conditions: list[str] | None = Field(
        None, description="Conditions to filter by, e.g. ['vegetarian', 'wheelchair']."
    )
    filter_type: str | None = Field(
        None,
        description="Filter type: 'circle' (lon,lat,radiusM), 'rect' (lon1,lat1,lon2,lat2), 'place', or 'geometry'.",
    )
    filter_value: str | None = Field(
        None, description="Filter value matching filter_type, e.g. '-0.0707,51.5085,1000' for a circle."
    )
    bias: str | None = Field(None, description="Proximity bias as 'lon,lat'.")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results (1-100).")
    offset: int = Field(0, ge=0, description="Pagination offset.")
    lang: str = Field("en", description="ISO 639-1 language code for results.")


class GeoapifyPlacesTool(BaseTool):
    """Search points of interest via the Geoapify Places API (requires GEOAPIFY_API_KEY)."""

    name: str = "geoapify_places_search"
    description: str = (
        "Search for points of interest (restaurants, shops, attractions) using the Geoapify "
        "Places API, filtered by categories, conditions, and a location (circle/rect/place)."
    )
    args_schema: type[BaseModel] = GeoapifyPlacesInput

    @api_tool(provider="Geoapify", endpoint="Places")
    def _run(
        self,
        categories: list[str] | None = None,
        conditions: list[str] | None = None,
        filter_type: str | None = None,
        filter_value: str | None = None,
        bias: str | None = None,
        limit: int = 20,
        offset: int = 0,
        lang: str = "en",
    ) -> str:
        """Query the Geoapify Places API and return the GeoJSON FeatureCollection."""
        api_key = os.getenv("GEOAPIFY_API_KEY")
        if not api_key:
            return err("GEOAPIFY_API_KEY not configured")
        if filter_type and not filter_value:
            return err("filter_value is required when filter_type is set")

        params: dict[str, Any] = {"apiKey": api_key, "limit": limit, "lang": lang}
        if categories:
            params["categories"] = ",".join(categories)
        if conditions:
            params["conditions"] = ",".join(conditions)
        if filter_type and filter_value:
            params["filter"] = f"{filter_type}:{filter_value}"
        if bias:
            params["bias"] = f"proximity:{bias}"
        if offset:
            params["offset"] = offset

        response = requests.get("https://api.geoapify.com/v2/places", params=params, timeout=30)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and "error" in result:
            return err(f"Geoapify API error: {result.get('message', 'unknown error')}")
        return ok(result)
