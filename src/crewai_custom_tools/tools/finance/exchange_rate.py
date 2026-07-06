"""Exchange Rates Tool using OpenExchangeRates API."""

import logging
import os
import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from crewai_custom_tools.core.decorators import api_tool

logger = logging.getLogger(__name__)


from crewai_custom_tools.models import ExchangeRateToolInput


class ExchangeRateTool(BaseTool):
    """A tool to fetch fiat currency exchange rates."""

    name: str = "exchange_rates"
    description: str = (
        "Fetches the latest fiat exchange rates for specified currencies using OpenExchangeRates API. "
        "Requires OPENEXCHANGERATES_API_KEY environment variable."
    )
    args_schema: type[BaseModel] = ExchangeRateToolInput

    @api_tool(
        provider="OpenExchangeRates",
        endpoint="LatestRates",
        default_return="Error: Exchange rates request failed.",
    )
    def _run(
        self, base_currency: str = "USD", target_currencies: Optional[List[str]] = None
    ) -> str:
        """Fetch latest exchange rates."""
        api_key = os.getenv("OPENEXCHANGERATES_API_KEY")
        if not api_key:
            return "Error: OPENEXCHANGERATES_API_KEY environment variable not set."

        base_url = "https://openexchangerates.org/api/latest.json"
        params = {"app_id": api_key, "base": base_currency}

        if target_currencies:
            params["symbols"] = ",".join(target_currencies)

        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            return f"API Error: {data.get('description', 'Unknown error from OpenExchangeRates API.')}"

        rates = data.get("rates")
        if not rates:
            return "Error: Could not retrieve exchange rates from the API response."

        if target_currencies:
            output_rates = {
                curr: rates.get(curr) for curr in target_currencies if curr in rates
            }
        else:
            output_rates = rates

        if not output_rates:
            return f"Error: No rates found for the specified target currencies: {target_currencies} with base {base_currency}"

        return (
            f"Exchange rates based on {data.get('base', base_currency)}: {output_rates}"
        )
