from vnpy.web.services.cb_quant_service import CbQuantService
from vnpy.web.services.cb_market_service import CbMarketService
from vnpy.web.services.cb_catalog_service import CbCatalogService
from vnpy.web.services.cb_history_service import CbHistoryService

cb_history_service = CbHistoryService()
cb_quant_service = CbQuantService()
cb_market_service = CbMarketService()
cb_catalog_service = CbCatalogService()

__all__ = [
    "CbQuantService",
    "CbMarketService",
    "CbCatalogService",
    "CbHistoryService",
    "cb_history_service",
    "cb_quant_service",
    "cb_market_service",
    "cb_catalog_service",
]
