"""AccuWeather API meteorological conditions tool."""

import logging
import os
from typing import Optional

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel

from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.core.results import err, ok
from crewai_custom_tools.models.accuweather_models import AccuWeatherToolInput

logger = logging.getLogger(__name__)

# HTTPS so the apikey query param is never sent in cleartext.
_BASE_URL = "https://dataservice.accuweather.com"


class AccuWeatherTool(BaseTool):
    """Get current weather conditions from AccuWeather."""

    name: str = "get_current_weather"
    description: str = (
        "A tool to get the current weather conditions for a specific location."
    )
    args_schema: type[BaseModel] = AccuWeatherToolInput

    def _get_location_key(self, location: str, api_key: str) -> str:
        """Get the location key for a given location name."""
        url = f"{_BASE_URL}/locations/v1/cities/autocomplete"
        params = {"apikey": api_key, "q": location}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            raise ValueError(f"Location '{location}' not found.")
        return str(data[0]["Key"])

    def _get_current_conditions(
        self, location_key: str, api_key: str
    ) -> dict | None:
        """Get the current weather conditions for a given location key."""
        url = f"{_BASE_URL}/currentconditions/v1/{location_key}"
        params = {"apikey": api_key}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            return None

        weather_info = data[0]
        metric = weather_info["Temperature"]["Metric"]
        return {
            "temperature": metric["Value"],
            "unit": metric["Unit"],
            "conditions": weather_info["WeatherText"],
        }

    @api_tool(provider="AccuWeather", endpoint="CurrentConditions")
    def _run(self, location: str) -> str:
        """Run the AccuWeather lookup."""
        api_key = os.getenv("ACCUWEATHER_API_KEY")
        if not api_key:
            return err("ACCUWEATHER_API_KEY environment variable not set")

        location_key = self._get_location_key(location, api_key)
        conditions = self._get_current_conditions(location_key, api_key)
        if conditions is None:
            return err(f"Could not retrieve weather data for {location!r}")
        return ok({"location": location, **conditions})
