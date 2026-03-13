from __future__ import annotations

from vnpy.web.services.cb_catalog_service import CbCatalogService
from vnpy.web.services.cb_history_service import CbHistoryService
from vnpy.web.services.cb_market_service import CbMarketService
from vnpy.web.services.cb_quant_service import CbQuantService
from vnpy.web.services.cb_tushare_service import CbTushareService

_cb_history_service: CbHistoryService | None = None
_cb_quant_service: CbQuantService | None = None
_cb_market_service: CbMarketService | None = None
_cb_catalog_service: CbCatalogService | None = None
_cb_tushare_service: CbTushareService | None = None


def __getattr__(name: str):
    global _cb_history_service, _cb_quant_service, _cb_market_service, _cb_catalog_service, _cb_tushare_service

    if name == "cb_history_service":
        if _cb_history_service is None:
            _cb_history_service = CbHistoryService()
        return _cb_history_service
    if name == "cb_quant_service":
        if _cb_quant_service is None:
            _cb_quant_service = CbQuantService()
        return _cb_quant_service
    if name == "cb_market_service":
        if _cb_market_service is None:
            _cb_market_service = CbMarketService()
        return _cb_market_service
    if name == "cb_catalog_service":
        if _cb_catalog_service is None:
            _cb_catalog_service = CbCatalogService()
        return _cb_catalog_service
    if name == "cb_tushare_service":
        if _cb_tushare_service is None:
            _cb_tushare_service = CbTushareService()
        return _cb_tushare_service
    raise AttributeError(name)


__all__ = [
    "CbQuantService",
    "CbMarketService",
    "CbCatalogService",
    "CbHistoryService",
    "CbTushareService",
    "cb_history_service",
    "cb_quant_service",
    "cb_market_service",
    "cb_catalog_service",
    "cb_tushare_service",
]
