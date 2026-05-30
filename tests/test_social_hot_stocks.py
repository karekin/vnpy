from __future__ import annotations

import pytest
import requests

from vnpy.web.api.social_hot_stocks import get_social_hot_stocks
from vnpy.web.domain.social_hot_stocks import SocialHotStocksStore
from vnpy.web.services.social_hot_stocks_service import SocialHotStocksService


class _FakeResponse:
    def __init__(self, payload: dict, status_error: Exception | None = None) -> None:
        self._payload = payload
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error:
            raise self._status_error

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> _FakeResponse:
        self.calls.append(url)
        return _FakeResponse(self.payload)


class _PagedFakeSession:
    def __init__(self, payloads: dict[int, dict]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> _FakeResponse:
        self.calls.append(url)
        page = int(url.rsplit("/", 1)[-1])
        return _FakeResponse(self.payloads[page])


class _FailingSession:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, **_: object) -> _FakeResponse:
        self.calls.append(url)
        return _FakeResponse({}, requests.Timeout("timeout"))


def test_social_hot_stocks_service_maps_apewisdom_response() -> None:
    session = _FakeSession(
        {
            "count": 2,
            "pages": 1,
            "current_page": 1,
            "results": [
                {
                    "rank": 1,
                    "ticker": "NVDA",
                    "name": "NVIDIA",
                    "mentions": "350",
                    "upvotes": "1721",
                    "rank_24h_ago": "5",
                    "mentions_24h_ago": "332",
                },
                {
                    "rank": 2,
                    "ticker": "SPY",
                    "name": "SPDR S&amp;P 500 ETF Trust",
                    "mentions": 259,
                    "upvotes": 767,
                    "rank_24h_ago": 4,
                    "mentions_24h_ago": 366,
                },
            ],
        }
    )
    service = SocialHotStocksService(session=session, store=None)  # type: ignore[arg-type]

    response = service.get_hot_stocks(source_filter="all-stocks", limit=2)

    assert session.calls == ["https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"]
    assert response.count == 2
    assert response.page == 1
    assert response.page_size == 2
    assert response.returned_count == 2
    assert response.cache_status == "live"
    assert response.items[0].symbol == "NVDA"
    assert response.items[0].mention_change == 18
    assert response.items[0].mention_change_pct == 5.4
    assert response.items[0].rank_change == 4
    assert response.items[1].name == "SPDR S&P 500 ETF Trust"
    assert response.items[1].mention_change == -107


def test_social_hot_stocks_service_paginates_across_apewisdom_pages() -> None:
    session = _PagedFakeSession(
        {
            1: {
                "count": 4,
                "pages": 2,
                "current_page": 1,
                "results": [
                    {"rank": 1, "ticker": "NVDA", "name": "NVIDIA", "mentions": 10, "upvotes": 100},
                    {"rank": 2, "ticker": "MSFT", "name": "Microsoft", "mentions": 9, "upvotes": 90},
                ],
            },
            2: {
                "count": 4,
                "pages": 2,
                "current_page": 2,
                "results": [
                    {"rank": 3, "ticker": "AAPL", "name": "Apple", "mentions": 8, "upvotes": 80},
                    {"rank": 4, "ticker": "TSLA", "name": "Tesla", "mentions": 7, "upvotes": 70},
                ],
            },
        }
    )
    service = SocialHotStocksService(session=session, store=None)  # type: ignore[arg-type]

    response = service.get_hot_stocks(source_filter="all-stocks", page=2, page_size=2)

    assert response.page == 2
    assert response.page_size == 2
    assert response.total_pages == 2
    assert response.returned_count == 2
    assert [item.symbol for item in response.items] == ["AAPL", "TSLA"]
    assert session.calls == [
        "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1",
        "https://apewisdom.io/api/v1.0/filter/all-stocks/page/2",
    ]


def test_social_hot_stocks_service_persists_and_reuses_snapshot(tmp_path) -> None:
    store = SocialHotStocksStore(tmp_path / "social_hot.db")
    session = _FakeSession(
        {
            "count": 2,
            "pages": 1,
            "current_page": 1,
            "results": [
                {"rank": 1, "ticker": "NVDA", "name": "NVIDIA", "mentions": 10, "upvotes": 100},
                {"rank": 2, "ticker": "MSFT", "name": "Microsoft", "mentions": 9, "upvotes": 90},
            ],
        }
    )
    service = SocialHotStocksService(session=session, store=store)  # type: ignore[arg-type]

    live_response = service.get_hot_stocks(source_filter="all-stocks", page=1, page_size=2)

    assert live_response.snapshot_id is not None
    assert live_response.persisted_at is not None

    failing_session = _FailingSession()
    restarted_service = SocialHotStocksService(session=failing_session, store=store)  # type: ignore[arg-type]
    cached_response = restarted_service.get_hot_stocks(source_filter="all-stocks", page=1, page_size=2)

    assert cached_response.cache_status == "persisted-cache"
    assert cached_response.snapshot_id == live_response.snapshot_id
    assert [item.symbol for item in cached_response.items] == ["NVDA", "MSFT"]
    assert failing_session.calls == []


def test_social_hot_stocks_service_falls_back_to_persisted_snapshot(tmp_path) -> None:
    store = SocialHotStocksStore(tmp_path / "social_hot.db")
    session = _FakeSession(
        {
            "count": 1,
            "pages": 1,
            "current_page": 1,
            "results": [{"rank": 1, "ticker": "NVDA", "name": "NVIDIA", "mentions": 10, "upvotes": 100}],
        }
    )
    service = SocialHotStocksService(session=session, store=store)  # type: ignore[arg-type]
    service.get_hot_stocks(source_filter="all-stocks", page=1, page_size=1)

    failing_service = SocialHotStocksService(session=_FailingSession(), store=store)  # type: ignore[arg-type]
    response = failing_service.get_hot_stocks(source_filter="all-stocks", page=1, page_size=1, refresh=True)

    assert response.cache_status == "persisted-fallback"
    assert response.items[0].symbol == "NVDA"


def test_social_hot_stocks_service_rejects_unknown_filter() -> None:
    service = SocialHotStocksService(session=_FakeSession({}), store=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="unsupported ApeWisdom filter"):
        service.get_hot_stocks(source_filter="not-a-board")


def test_social_hot_stocks_api_maps_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenService:
        def get_hot_stocks(self, **_: object):
            raise requests.Timeout("timeout")

    import vnpy.web.services as services

    monkeypatch.setattr(services, "social_hot_service", _BrokenService(), raising=False)

    with pytest.raises(Exception) as exc_info:
        get_social_hot_stocks()

    assert getattr(exc_info.value, "status_code", None) == 502
