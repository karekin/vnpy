from __future__ import annotations

import builtins
import importlib
import sys
import types

import vnpy.web.services as services


def test_services_module_should_lazy_create_singletons(monkeypatch) -> None:
    created: list[str] = []

    class _FakeQuantService:
        def __init__(self) -> None:
            created.append("quant")

    monkeypatch.setattr(services, "_quant_service", None)
    monkeypatch.setattr(services, "CbQuantService", _FakeQuantService)
    services.__dict__.pop("quant_service", None)

    first = services.quant_service
    second = services.quant_service

    assert isinstance(first, _FakeQuantService)
    assert first is second
    assert created == ["quant"]


def test_services_module_should_not_import_tenx_service_eagerly(monkeypatch) -> None:
    attempted: list[str] = []
    real_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "vnpy.web.services.tenx_hunter_service":
            attempted.append(name)
            raise AssertionError("TenxHunterService should not be imported while loading vnpy.web.services")
        return real_import(name, globals, locals, fromlist, level)

    sys.modules.pop("vnpy.web.services", None)
    monkeypatch.setattr(builtins, "__import__", _guarded_import)

    module = importlib.import_module("vnpy.web.services")

    assert attempted == []
    assert getattr(module, "_tenx_service") is None


def test_services_module_should_lazy_create_tenx_singleton(monkeypatch) -> None:
    created: list[str] = []

    fake_module = types.ModuleType("vnpy.web.services.tenx_hunter_service")

    class _FakeTenxHunterService:
        def __init__(self) -> None:
            created.append("tenx")

    fake_module.TenxHunterService = _FakeTenxHunterService

    sys.modules.pop("vnpy.web.services", None)
    monkeypatch.setitem(sys.modules, "vnpy.web.services.tenx_hunter_service", fake_module)

    module = importlib.import_module("vnpy.web.services")
    first = module.tenx_service
    second = module.tenx_service

    assert isinstance(first, _FakeTenxHunterService)
    assert first is second
    assert created == ["tenx"]


def test_services_module_should_lazy_create_smart_allocation_singleton(monkeypatch) -> None:
    created: list[str] = []

    fake_module = types.ModuleType("vnpy.web.services.smart_allocation_service")

    class _FakeSmartAllocationService:
        def __init__(self) -> None:
            created.append("smart-allocation")

    fake_module.SmartAllocationService = _FakeSmartAllocationService

    sys.modules.pop("vnpy.web.services", None)
    monkeypatch.setitem(sys.modules, "vnpy.web.services.smart_allocation_service", fake_module)

    module = importlib.import_module("vnpy.web.services")
    first = module.allocation_service
    second = module.allocation_service

    assert isinstance(first, _FakeSmartAllocationService)
    assert first is second
    assert created == ["smart-allocation"]
