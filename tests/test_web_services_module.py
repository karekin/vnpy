from __future__ import annotations

import vnpy.web.services as services


def test_services_module_should_lazy_create_singletons(monkeypatch) -> None:
    created: list[str] = []

    class _FakeQuantService:
        def __init__(self) -> None:
            created.append("quant")

    monkeypatch.setattr(services, "_cb_quant_service", None)
    monkeypatch.setattr(services, "CbQuantService", _FakeQuantService)
    monkeypatch.delattr(services, "cb_quant_service", raising=False)

    first = services.cb_quant_service
    second = services.cb_quant_service

    assert isinstance(first, _FakeQuantService)
    assert first is second
    assert created == ["quant"]
