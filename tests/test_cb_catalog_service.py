from __future__ import annotations

from vnpy.web.services.cb_catalog_service import CbCatalogService


def test_list_factors_should_keep_full_factor_catalog_visible() -> None:
    service = CbCatalogService()

    payload = service.list_factors(category="all", enabled_only=True)
    factors = {
        factor.factor_key: factor
        for category in payload.items
        for factor in category.factors
    }

    assert "dblow" in factors
    assert "close" in factors
    assert "conv_prem" in factors
    assert "price_benchmark" in factors
    assert factors["dblow"].template_selectable is True
    assert factors["open"].template_selectable is True
    assert factors["bias_5"].template_selectable is False
    assert factors["dblow"].support_level == "strong"
    assert factors["bias_5"].support_level == "disabled"
