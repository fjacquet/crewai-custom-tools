"""Smoke tests for package level exports."""


def test_package_exports():
    from crewai_custom_tools import (
        CoinMarketCapInfoTool,
        EpieosEmailLookupTool,
        FREDMacroTool,
        GitHubSearchTool,
        HoleheEmailScannerTool,
        HtmlToPdfTool,
        OpenCorporatesSearchTool,
        PerplexitySearchTool,
        RenderReportTool,
        SerperSearchTool,
        TodoistTool,
        UnifiedScraperTool,
        YahooFinanceNewsTool,
        YahooFinanceTickerInfoTool,
    )

    assert PerplexitySearchTool is not None
    assert YahooFinanceTickerInfoTool is not None
    assert YahooFinanceNewsTool is not None
    assert SerperSearchTool is not None
    assert UnifiedScraperTool is not None
    assert CoinMarketCapInfoTool is not None
    assert FREDMacroTool is not None
    assert GitHubSearchTool is not None
    assert RenderReportTool is not None
    assert HtmlToPdfTool is not None
    assert TodoistTool is not None
    assert EpieosEmailLookupTool is not None
    assert HoleheEmailScannerTool is not None
    assert OpenCorporatesSearchTool is not None
