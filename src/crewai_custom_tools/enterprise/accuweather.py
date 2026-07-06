"""AccuWeather API meteorological conditions tool."""

import logging
import os
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel
from crewai_custom_tools.core.decorators import api_tool
from crewai_custom_tools.models.accuweather_models import AccuWeatherToolInput

logger = logging.getLogger(__name__)


class AccuWeatherTool(BaseTool):
    """Get current weather conditions from AccuWeather."""

    name: str = "get_current_weather"
    description: str = (
        "A tool to get the current weather conditions for a specific location."
    )
    args_schema: type[BaseModel] = AccuWeatherToolInput

    def _get_location_key(self, location: str, api_key: str) -> str:
        """Get the location key for a given location name."""
        url = "http://dataservice.accuweather.com/locations/v1/cities/autocomplete"
        params = {"apikey": api_key, "q": location}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            raise ValueError(f"Location '{location}' not found.")
        return str(data[0]["Key"])

    def _get_current_conditions(self, location_key: str, api_key: str) -> str:
        """Get the current weather conditions for a given location key."""
        url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}"
        params = {"apikey": api_key}
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            return "Could not retrieve weather data."

        weather_info = data[0]
        temp = weather_info["Temperature"]["Metric"]["Value"]
        unit = weather_info["Temperature"]["Metric"]["Unit"]
        weather_text = weather_info["WeatherText"]
        return f"Current weather in your location: {temp}°{unit}, {weather_text}."

    @api_tool(
        provider="AccuWeather",
        endpoint="CurrentConditions",
        default_return="Error: Weather lookup failed.",
    )
    def _run(self, location: str) -> str:
        """Run the AccuWeather lookup."""
        api_key = os.getenv("ACCUWEATHER_API_KEY")
        if not api_key:
            return "Error: ACCUWEATHER_API_KEY environment variable not set."

        location_key = self._get_location_key(location, api_key)
        return self._get_current_conditions(location_key, api_key)
