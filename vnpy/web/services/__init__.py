from __future__ import annotations

"""Lazy singleton exports for web services.

Use collision-free singleton names so `from vnpy.web.services import ...`
does not resolve to same-named submodules.
"""

from typing import TYPE_CHECKING

from vnpy.web.services.cb_catalog_service import CbCatalogService
from vnpy.web.services.deerflow_service import DeerFlowService
from vnpy.web.services.cb_history_service import CbHistoryService
from vnpy.web.services.cb_market_service import CbMarketService
from vnpy.web.services.cb_quant_service import CbQuantService
from vnpy.web.services.cb_tushare_service import CbTushareService

if TYPE_CHECKING:
    from vnpy.web.services.investment_copilot_service import InvestmentCopilotService
    from vnpy.web.services.smart_allocation_service import SmartAllocationService
    from vnpy.web.services.social_hot_stocks_service import SocialHotStocksService
    from vnpy.web.services.tenx_hunter_service import TenxHunterService

_history_service: CbHistoryService | None = None
_quant_service: CbQuantService | None = None
_market_service: CbMarketService | None = None
_catalog_service: CbCatalogService | None = None
_tushare_service: CbTushareService | None = None
_tenx_service: TenxHunterService | None = None
_deerflow_agent_service: DeerFlowService | None = None
_allocation_service: SmartAllocationService | None = None
_investment_copilot_service: InvestmentCopilotService | None = None
_social_hot_service: SocialHotStocksService | None = None


def __getattr__(name: str):
    global _history_service, _quant_service, _market_service, _catalog_service, _tushare_service, _tenx_service, _deerflow_agent_service, _allocation_service, _investment_copilot_service, _social_hot_service

    if name == "history_service":
        if _history_service is None:
            _history_service = CbHistoryService()
        return _history_service
    if name == "quant_service":
        if _quant_service is None:
            _quant_service = CbQuantService()
        return _quant_service
    if name == "market_service":
        if _market_service is None:
            _market_service = CbMarketService()
        return _market_service
    if name == "catalog_service":
        if _catalog_service is None:
            _catalog_service = CbCatalogService()
        return _catalog_service
    if name == "tushare_service":
        if _tushare_service is None:
            _tushare_service = CbTushareService()
        return _tushare_service
    if name == "TenxHunterService":
        from vnpy.web.services.tenx_hunter_service import TenxHunterService

        return TenxHunterService
    if name == "tenx_service":
        if _tenx_service is None:
            from vnpy.web.services.tenx_hunter_service import TenxHunterService

            _tenx_service = TenxHunterService()
        return _tenx_service
    if name == "deerflow_agent_service":
        if _deerflow_agent_service is None:
            _deerflow_agent_service = DeerFlowService()
        return _deerflow_agent_service
    if name == "SmartAllocationService":
        from vnpy.web.services.smart_allocation_service import SmartAllocationService

        return SmartAllocationService
    if name == "allocation_service":
        if _allocation_service is None:
            from vnpy.web.services.smart_allocation_service import SmartAllocationService

            _allocation_service = SmartAllocationService()
        return _allocation_service
    if name == "InvestmentCopilotService":
        from vnpy.web.services.investment_copilot_service import InvestmentCopilotService

        return InvestmentCopilotService
    if name == "investment_copilot_service":
        if _investment_copilot_service is None:
            from vnpy.web.services.investment_copilot_service import InvestmentCopilotService

            _investment_copilot_service = InvestmentCopilotService()
        return _investment_copilot_service
    if name == "SocialHotStocksService":
        from vnpy.web.services.social_hot_stocks_service import SocialHotStocksService

        return SocialHotStocksService
    if name == "social_hot_service":
        if _social_hot_service is None:
            from vnpy.web.services.social_hot_stocks_service import SocialHotStocksService

            _social_hot_service = SocialHotStocksService()
        return _social_hot_service
    raise AttributeError(name)


__all__ = [
    "CbQuantService",
    "CbMarketService",
    "CbCatalogService",
    "CbHistoryService",
    "CbTushareService",
    "TenxHunterService",
    "SmartAllocationService",
    "InvestmentCopilotService",
    "SocialHotStocksService",
    "history_service",
    "quant_service",
    "market_service",
    "catalog_service",
    "tushare_service",
    "tenx_service",
    "deerflow_agent_service",
    "allocation_service",
    "investment_copilot_service",
    "social_hot_service",
]
