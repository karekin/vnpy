from __future__ import annotations

from datetime import date
import importlib
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from vnpy.web.domain.cb_quant.history_store import CbHistoryStore
from vnpy.web.domain.cb_quant.tushare_store import CbTushareStore
from vnpy.web.services.cb_tushare_service import CbTushareService

cb_tushare_module = importlib.import_module("vnpy.web.services.cb_tushare_service")


class _FakeTushareClientSuccess:
    def __init__(self, token: str, *, http_url: str) -> None:
        self.token = token
        self.http_url = http_url

    def query(self, api_name: str, **params: Any) -> pd.DataFrame:
        if api_name == "trade_cal":
            return pd.DataFrame(
                [
                    {"cal_date": "20240129", "is_open": "1"},
                    {"cal_date": "20240130", "is_open": "1"},
                ]
            )

        if api_name == "cb_basic":
            return pd.DataFrame(
                [
                    {
                        "ts_code": "110001.SH",
                        "bond_short_name": "CB-ONE",
                        "stk_code": "600000.SH",
                        "stk_short_name": "STK-ONE",
                        "maturity_date": "2028-12-31",
                        "list_date": "20240101",
                        "conv_start_date": "20240201",
                        "value_date": "20240101",
                        "conv_price": 10.0,
                        "issue_size": "12",
                        "remain_size": "12",
                        "rating": "AA+",
                    },
                    {
                        "ts_code": "110002.SH",
                        "bond_short_name": "CB-TWO",
                        "stk_code": "000001.SZ",
                        "stk_short_name": "STK-TWO",
                        "maturity_date": "2027-06-30",
                        "list_date": "20240101",
                        "conv_start_date": "20240201",
                        "value_date": "20240101",
                        "conv_price": 8.0,
                        "issue_size": "8",
                        "remain_size": "8",
                        "rating": "AA",
                    },
                ]
            )

        if api_name == "cb_daily":
            trade_date = str(params.get("trade_date", ""))
            if trade_date not in {"20240129", "20240130"}:
                return pd.DataFrame()
            return pd.DataFrame(
                [
                    {
                        "ts_code": "110001.SH",
                        "trade_date": trade_date,
                        "pre_close": 100.0 if trade_date == "20240129" else 101.0,
                        "close": 101.0 if trade_date == "20240129" else 102.0,
                        "pct_chg": 1.0 if trade_date == "20240129" else 0.99,
                        "amount": 2345.6,
                        "bond_prem": 22.5,
                        "bond_value": 89.0,
                    },
                    {
                        "ts_code": "110002.SH",
                        "trade_date": trade_date,
                        "pre_close": 98.0 if trade_date == "20240129" else 97.5,
                        "close": 98.0 if trade_date == "20240129" else 97.5,
                        "pct_chg": -0.51,
                        "amount": 1234.5,
                        "bond_prem": 18.5,
                        "bond_value": 86.0,
                    },
                ]
            )

        if api_name == "daily":
            codes = [item for item in str(params.get("ts_code", "")).split(",") if item]
            trade_date = str(params.get("trade_date", ""))
            rows = []
            for idx, code in enumerate(codes):
                rows.append(
                    {
                        "ts_code": code,
                        "trade_date": trade_date,
                        "close": 101.0 + idx,
                        "pct_chg": 1.2 + idx,
                    }
                )
            return pd.DataFrame(rows)

        if api_name == "daily_basic":
            codes = [item for item in str(params.get("ts_code", "")).split(",") if item]
            trade_date = str(params.get("trade_date", ""))
            rows = []
            for idx, code in enumerate(codes):
                rows.append(
                    {
                        "ts_code": code,
                        "trade_date": trade_date,
                        "pb": 1.4 + idx * 0.1,
                        "total_mv": 600000 + idx * 10000,
                    }
                )
            return pd.DataFrame(rows)

        if api_name == "cb_call":
            return pd.DataFrame(
                [
                    {
                        "ts_code": "110001.SH",
                        "ann_date": "20240129",
                        "call_type": "强赎",
                        "is_call": "公告提示强赎",
                        "call_reg_date": "20240202",
                        "call_date": "20240205",
                        "payment_date": "20240206",
                    }
                ]
            )

        if api_name in {"cb_issue", "cb_price_chg", "cb_share", "cb_rate"}:
            return pd.DataFrame(
                [
                    {
                        "ts_code": "110001.SH",
                        "ann_date": "20240129",
                        "event": api_name,
                    }
                ]
            )

        return pd.DataFrame()


class _FakeTushareClientFailure:
    def __init__(self, token: str, *, http_url: str) -> None:
        self.token = token
        self.http_url = http_url

    def query(self, api_name: str, **params: Any) -> pd.DataFrame:
        raise RuntimeError(f"simulated upstream error: {api_name}, {params}")


@pytest.fixture
def isolated_service(tmp_path: Path) -> CbTushareService:
    service = object.__new__(CbTushareService)
    service._store = CbTushareStore(tmp_path / "cb_tushare.db")
    service._history_store = CbHistoryStore(tmp_path / "cb_snapshots.db")
    return service


class TestCbTushareServiceSyncRangeSuccess:
    def test_sync_range_success(self, isolated_service: CbTushareService, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cb_tushare_module, "_TushareClient", _FakeTushareClientSuccess)
        monkeypatch.setattr(CbTushareService, "_load_token", staticmethod(lambda: "unit-token"))
        monkeypatch.setattr(CbTushareService, "_load_http_url", staticmethod(lambda: "http://unit.test"))

        payload = isolated_service.sync_range(
            start_date=date(2024, 1, 29),
            end_date=date(2024, 1, 30),
            mode="unit-test",
            max_trade_days=10,
        )

        assert payload["ok"] is True
        assert payload["trade_days"] == 2
        assert payload["cb_daily_rows"] == 4
        assert payload["stock_daily_rows"] == 4
        assert payload["factor_rows"] == 4
        assert payload["snapshot_rows"] == 4
        assert payload["event_rows"] == 5

        summary = isolated_service.get_summary()
        assert summary.cb_trade_days == 2
        assert summary.factor_trade_days == 2
        assert summary.event_rows == 5

        history_summary = isolated_service._history_store.get_summary()
        assert history_summary.snapshot_count == 2
        assert history_summary.date_start == "2024-01-29"
        assert history_summary.date_end == "2024-01-30"

        latest_log = isolated_service.latest_sync_log()
        assert latest_log is not None
        assert latest_log.status == "ok"
        assert latest_log.trade_days == 2

        dataset = isolated_service._history_store.load_market_dataset()
        frames = {trade_date: frame for trade_date, frame in dataset}
        first_day = frames["2024-01-29"]
        assert int(first_day.loc["110001", "days_to_redeem"]) == 4
        assert first_day.loc["110001", "redeem_status"] == "公告提示强赎"
        assert bool(first_day.loc["110001", "is_redeem_triggered"]) is False
        assert "price_fill_source" not in first_day.columns
        assert "stock_ts_code" not in first_day.columns
        assert "data_source" in first_day.columns


class TestCbTushareServiceSyncRangeFailure:
    def test_sync_range_failure_logs_failed_status(
        self, isolated_service: CbTushareService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(cb_tushare_module, "_TushareClient", _FakeTushareClientFailure)
        monkeypatch.setattr(CbTushareService, "_load_token", staticmethod(lambda: "unit-token"))
        monkeypatch.setattr(CbTushareService, "_load_http_url", staticmethod(lambda: "http://unit.test"))

        with pytest.raises(RuntimeError) as exc_info:
            isolated_service.sync_range(
                start_date=date(2024, 1, 29),
                end_date=date(2024, 1, 30),
                mode="unit-test-fail",
                max_trade_days=10,
            )

        assert "simulated upstream error" in str(exc_info.value)

        latest_log = isolated_service.latest_sync_log()
        assert latest_log is not None
        assert latest_log.status == "failed"
        assert latest_log.trade_days == 0
        assert "simulated upstream error" in latest_log.message


class TestCbTusharePriceCleaning:
    def test_normalize_price_priority(self) -> None:
        price, source = CbTushareService._normalize_price(
            close_price=102.3,
            pre_close_price=99.8,
            previous_valid_price=88.0,
        )
        assert price == 102.3
        assert source == "close"

    def test_build_rows_should_fill_from_pre_close(
        self,
        isolated_service: CbTushareService,
    ) -> None:
        cache: dict[str, float] = {}
        factor_rows, snapshot_rows = isolated_service._build_factor_and_snapshot_rows(
            trade_date="2024-01-30",
            cb_daily_rows=[
                {
                    "ts_code": "110001.SH",
                    "close": 0.0,
                    "pre_close": 101.5,
                    "bond_prem": 21.0,
                    "bond_value": 88.0,
                }
            ],
            cb_basic_map={
                "110001.SH": {
                    "bond_short_name": "CB-ONE",
                    "stk_code": "600000",
                    "maturity_date": "2028-12-31",
                    "issue_size": "12",
                }
            },
            stock_daily_map={"600000.SH": {"pct_chg": 2.0}},
            stock_basic_map={"600000.SH": {"pb": 1.66, "total_mv": 900000}},
            last_valid_price_map=cache,
        )

        assert len(factor_rows) == 1
        assert len(snapshot_rows) == 1
        assert factor_rows[0]["close_price"] == 101.5
        assert factor_rows[0]["price_fill_source"] == "pre_close"
        assert cache["110001"] == 101.5

    def test_build_rows_should_fill_from_previous_valid_price(
        self,
        isolated_service: CbTushareService,
    ) -> None:
        isolated_service._store.upsert_factor_rows(
            trade_date="2024-01-29",
            rows=[
                {
                    "trade_date": "2024-01-29",
                    "bond_code": "110001",
                    "close_price": 88.8,
                    "data_source": "unit",
                }
            ],
        )

        cache: dict[str, float] = {}
        factor_rows, _snapshot_rows = isolated_service._build_factor_and_snapshot_rows(
            trade_date="2024-01-30",
            cb_daily_rows=[
                {
                    "ts_code": "110001.SH",
                    "close": 0.0,
                    "pre_close": 0.0,
                    "bond_prem": 21.0,
                    "bond_value": 88.0,
                }
            ],
            cb_basic_map={
                "110001.SH": {
                    "bond_short_name": "CB-ONE",
                    "stk_code": "600000",
                    "maturity_date": "2028-12-31",
                    "issue_size": "12",
                }
            },
            stock_daily_map={"600000.SH": {"pct_chg": 0.5}},
            stock_basic_map={"600000.SH": {"pb": 1.5, "total_mv": 800000}},
            last_valid_price_map=cache,
        )

        assert len(factor_rows) == 1
        assert factor_rows[0]["close_price"] == 88.8
        assert factor_rows[0]["price_fill_source"] == "prev_valid"
        assert cache["110001"] == 88.8


class TestCbTushareMarketRows:
    def test_is_listed_on_trade_date_should_exclude_matured_bond_without_delist_date(self) -> None:
        assert CbTushareService._is_listed_on_trade_date(
            basic={
                "list_date": "20180904",
                "maturity_date": "20240814",
                "delist_date": "",
                "remain_size": "359091200",
            },
            trade_date=date(2026, 3, 6),
        ) is False

    def test_build_market_rows_should_skip_zero_turnover_bonds(
        self,
        isolated_service: CbTushareService,
    ) -> None:
        rows = isolated_service._build_market_rows(
            trade_date="2026-03-06",
            as_of="2026-03-06",
            cb_daily_rows=[
                {
                    "ts_code": "127033.SZ",
                    "close": 89.726,
                    "pre_close": 89.726,
                    "pct_chg": 0.0,
                    "amount": 0.0,
                },
                {
                    "ts_code": "110001.SH",
                    "close": 102.0,
                    "pre_close": 101.0,
                    "pct_chg": 0.99,
                    "amount": 2345.6,
                },
            ],
            cb_basic_map={
                "127033.SZ": {
                    "bond_short_name": "中装转2",
                    "stk_code": "002822.SZ",
                    "stk_short_name": "ST中装",
                    "maturity_date": "2027-04-16",
                    "list_date": "20210524",
                    "conv_price": 3.79,
                    "remain_size": "9180800",
                    "issue_size": "1160000000",
                },
                "110001.SH": {
                    "bond_short_name": "CB-ONE",
                    "stk_code": "600000.SH",
                    "stk_short_name": "STK-ONE",
                    "maturity_date": "2028-12-31",
                    "list_date": "20240101",
                    "conv_price": 10.0,
                    "remain_size": "1200000000",
                    "issue_size": "1200000000",
                },
            },
            stock_daily_map={
                "002822.SZ": {"close": 3.39, "pct_chg": 0.3},
                "600000.SH": {"close": 101.0, "pct_chg": 1.2},
            },
            stock_basic_map={
                "600000.SH": {"pb": 1.4, "circ_mv": 600000},
            },
            min_volume_wan=0,
        )

        assert [row.bond_id for row in rows] == ["110001"]

    def test_build_market_rows_should_skip_bonds_in_maturity_redemption_stop_trade_window(
        self,
        isolated_service: CbTushareService,
    ) -> None:
        isolated_service._store.upsert_trade_calendar(
            [
                {"cal_date": "20260306", "is_open": "1"},
                {"cal_date": "20260309", "is_open": "1"},
                {"cal_date": "20260310", "is_open": "1"},
                {"cal_date": "20260311", "is_open": "1"},
            ]
        )
        isolated_service._store.upsert_cb_event_rows(
            event_type="cb_call",
            rows=[
                {
                    "ts_code": "110067.SH",
                    "call_type": "到赎",
                    "is_call": "公告到期赎回",
                    "ann_date": "20260203",
                    "call_date": "20260312",
                    "payment_date": "20260312",
                    "call_reg_date": "20260311",
                }
            ],
        )

        rows = isolated_service._build_market_rows(
            trade_date="2026-03-06",
            as_of="2026-03-09",
            cb_daily_rows=[
                {
                    "ts_code": "110067.SH",
                    "close": 106.999,
                    "pre_close": 107.014,
                    "pct_chg": -0.014,
                    "amount": 61526.3065,
                },
                {
                    "ts_code": "110001.SH",
                    "close": 102.0,
                    "pre_close": 101.0,
                    "pct_chg": 0.99,
                    "amount": 2345.6,
                },
            ],
            cb_basic_map={
                "110067.SH": {
                    "bond_short_name": "华安转债",
                    "stk_code": "600909.SH",
                    "stk_short_name": "华安证券",
                    "maturity_date": "20260312",
                    "delist_date": "20260312",
                    "list_date": "20200409",
                    "conv_price": 5.78,
                    "remain_size": "1092951165.66",
                    "issue_size": "2800000000",
                },
                "110001.SH": {
                    "bond_short_name": "CB-ONE",
                    "stk_code": "600000.SH",
                    "stk_short_name": "STK-ONE",
                    "maturity_date": "2028-12-31",
                    "list_date": "20240101",
                    "conv_price": 10.0,
                    "remain_size": "1200000000",
                    "issue_size": "1200000000",
                },
            },
            stock_daily_map={
                "600909.SH": {"close": 5.9, "pct_chg": 0.1},
                "600000.SH": {"close": 101.0, "pct_chg": 1.2},
            },
            stock_basic_map={
                "600909.SH": {"pb": 1.2, "circ_mv": 800000},
                "600000.SH": {"pb": 1.4, "circ_mv": 600000},
            },
            min_volume_wan=0,
        )

        assert [row.bond_id for row in rows] == ["110001"]

    def test_load_latest_market_rows_should_use_latest_trade_day_and_convert_units(
        self,
        isolated_service: CbTushareService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(cb_tushare_module, "_TushareClient", _FakeTushareClientSuccess)
        monkeypatch.setattr(CbTushareService, "_load_token", staticmethod(lambda: "unit-token"))
        monkeypatch.setattr(CbTushareService, "_load_http_url", staticmethod(lambda: "http://unit.test"))

        rows, source = isolated_service.load_latest_market_rows(min_volume_wan=0)

        assert source == "tushare.pro(2024-01-30)"
        assert len(rows) == 2
        assert rows[0].bond_id == "110001"
        assert rows[0].bond_name == "CB-ONE"
        assert rows[0].price == 102.0
        assert rows[0].amount_wan == 2345.6
        assert rows[0].stock_id == "sh600000"
        assert rows[0].stock_name == "STK-ONE"
        assert rows[0].convert_price == 10.0
        assert rows[0].convert_value == 1010.0
        assert rows[0].premium_rt == -89.9
        assert rows[0].source == "tushare.pro"


def _load_live_token_and_url() -> tuple[str | None, str]:
    local = CbTushareService._load_local_env_map()
    token = (
        os.getenv("TUSHARE_TOKEN")
        or os.getenv("TUSHARE_PRO_TOKEN")
        or local.get("TUSHARE_TOKEN")
        or local.get("TUSHARE_PRO_TOKEN")
    )
    http_url = os.getenv("TUSHARE_HTTP_URL") or local.get("TUSHARE_HTTP_URL") or "http://lianghua.nanyangqiankun.top"
    return token, http_url


@pytest.fixture(scope="module")
def live_client():
    ts = pytest.importorskip("tushare")
    token, http_url = _load_live_token_and_url()
    if not token:
        pytest.skip("TUSHARE token not found. Set TUSHARE_TOKEN/TUSHARE_PRO_TOKEN or .env.tushare.local")

    pro = ts.pro_api(token)
    pro._DataApi__token = token
    pro._DataApi__http_url = http_url
    return pro, token, http_url


class TestTushareLiveSuccess:
    def test_daily_example_should_return_rows(self, live_client) -> None:
        pro, _token, _http_url = live_client
        frame = pro.daily(ts_code="000001.SZ", start_date="20240101", end_date="20240131")
        assert isinstance(frame, pd.DataFrame)
        assert not frame.empty


class TestTushareLiveFailure:
    def test_daily_with_invalid_token_should_fail(self, live_client) -> None:
        ts = pytest.importorskip("tushare")
        _pro, _token, http_url = live_client

        bad = ts.pro_api("invalid-token-for-test")
        bad._DataApi__token = "invalid-token-for-test"
        bad._DataApi__http_url = http_url
        with pytest.raises(Exception):
            bad.daily(ts_code="000001.SZ", start_date="20240101", end_date="20240131")

    @pytest.mark.xfail(
        strict=False,
        reason="Some proxy tokens can query daily but are blocked on trade_cal/cb_* APIs.",
    )
    def test_core_sync_apis_should_work_for_full_backfill(self, live_client) -> None:
        pro, _token, _http_url = live_client

        trade_cal = pro.trade_cal(exchange="SSE", start_date="20240101", end_date="20240131", is_open="1")
        cb_daily = pro.cb_daily(trade_date="20240131")
        cb_basic = pro.cb_basic()

        assert isinstance(trade_cal, pd.DataFrame) and not trade_cal.empty
        assert isinstance(cb_daily, pd.DataFrame) and not cb_daily.empty
        assert isinstance(cb_basic, pd.DataFrame) and not cb_basic.empty
