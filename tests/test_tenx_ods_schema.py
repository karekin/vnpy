from __future__ import annotations

import csv
import hashlib
import unittest
from pathlib import Path

from vnpy.web.tenx_hunter import pipeline


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DATA_DIR = ROOT / "examples" / "tenx_hunter_data_pipeline" / "sample_data"


class FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params: tuple[object, ...] | None = None):
        self.calls.append((sql, tuple(params or ())))
        return self

    def fetchall(self):
        return []


class OdsSchemaTests(unittest.TestCase):
    def _load_csv_row(self, name: str) -> dict[str, object]:
        with (SAMPLE_DATA_DIR / name).open("r", encoding="utf-8") as handle:
            return next(csv.DictReader(handle))

    def test_schema_sql_keeps_only_main_chain_ods_tables(self) -> None:
        core_tables = [
            "ods.us_equity_price_daily_raw",
            "ods.security_financial_statement_raw",
            "ods.sec_filing_document_raw",
            "ods.security_news_article_raw",
            "ods.user_watch_action_raw",
        ]
        non_core_tables = [
            "ods.security_ticker_overview_polygon_raw",
            "ods.security_symbol_master_raw",
            "ods.security_industry_mapping_raw",
            "ods.theme_taxonomy_raw",
            "ods.security_news_polygon_raw",
            "ods.sec_submissions_raw",
            "ods.sec_companyfacts_raw",
            "ods.sec_submission_filing_raw",
            "ods.sec_companyfact_item_raw",
            "ods.security_earnings_calendar_raw",
            "ods.security_earnings_event_raw",
            "ods.security_analyst_estimate_item_raw",
            "ods.user_feedback_raw",
            "ods.macro_fred_series_raw",
            "ods.macro_fred_observation_raw",
            "ods.security_corporate_action_polygon_raw",
        ]

        for table in core_tables:
            self.assertIn(table, pipeline.SCHEMA_SQL)
        for table in non_core_tables:
            self.assertNotIn(table, pipeline.SCHEMA_SQL)

    def test_sync_sql_drops_non_core_ods_tables(self) -> None:
        self.assertIn("DROP TABLE IF EXISTS ods.sec_submissions_raw CASCADE;", pipeline.ODS_SCHEMA_SYNC_SQL)
        self.assertIn("DROP TABLE IF EXISTS ods.sec_companyfacts_raw CASCADE;", pipeline.ODS_SCHEMA_SYNC_SQL)
        self.assertIn("DROP TABLE IF EXISTS ods.security_news_polygon_raw CASCADE;", pipeline.ODS_SCHEMA_SYNC_SQL)
        self.assertIn("DROP TABLE IF EXISTS ods.macro_fred_series_raw CASCADE;", pipeline.ODS_SCHEMA_SYNC_SQL)
        self.assertIn("DROP TABLE IF EXISTS ods.security_corporate_action_polygon_raw CASCADE;", pipeline.ODS_SCHEMA_SYNC_SQL)

    def test_price_upsert_extracts_core_fields(self) -> None:
        row = self._load_csv_row("price_daily.csv")
        conn = FakeConn()

        pipeline._insert_price_rows(conn, [row])

        self.assertEqual(len(conn.calls), 1)
        sql, params = conn.calls[0]
        self.assertIn("ods.us_equity_price_daily_raw", sql)
        self.assertEqual(params[0], "NVDA")
        self.assertEqual(params[1], "2026-04-09")
        self.assertEqual(params[11], "polygon-demo")

    def test_schema_sql_removes_estimate_raw_from_main_chain(self) -> None:
        self.assertNotIn("ods.security_analyst_estimate_raw", pipeline.SCHEMA_SQL)
        self.assertIn("DROP TABLE IF EXISTS ods.security_analyst_estimate_raw CASCADE;", pipeline.ODS_SCHEMA_SYNC_SQL)
        self.assertIn("DROP TABLE IF EXISTS dwd.security_estimate_revision_daily CASCADE;", pipeline.ODS_SCHEMA_SYNC_SQL)

    def test_financial_upsert_populates_structured_metadata_columns(self) -> None:
        row = self._load_csv_row("financials.csv")
        conn = FakeConn()

        pipeline._insert_financial_rows(conn, [row])

        self.assertEqual(len(conn.calls), 1)
        sql, params = conn.calls[0]
        self.assertIn("ods.security_financial_statement_raw", sql)
        self.assertEqual(params[0], "NVDA")
        self.assertEqual(params[1], "2026-01-25")
        self.assertEqual(params[3], 2026)
        self.assertEqual(params[4], "annual")
        self.assertEqual(params[5], "2026-02-26")
        self.assertEqual(params[14], "0001045810-26-000023")
        self.assertEqual(params[15], "10-K")
        self.assertEqual(params[16], "USD")
        self.assertEqual(params[17], "parsed")

    def test_news_upsert_populates_polygon_metadata_columns(self) -> None:
        row = {
            "news_id": "news-1",
            "symbol": "NVDA",
            "published_time": "2026-04-12T05:25:00Z",
            "updated_time": "2026-04-12T06:00:00Z",
            "title": "Polygon news",
            "summary": "Summary text",
            "article_url": "https://example.com/article",
            "language": "en",
            "author": "Reporter",
            "publisher_name": "Example Media",
            "publisher_homepage": "https://example.com",
            "primary_symbol": "NVDA",
            "related_symbols": ["NVDA", "AVGO"],
            "object_key": "news/news-1.txt",
            "content": "Summary text",
            "source_vendor": "polygon-news",
            "raw_payload": {
                "id": "news-1",
                "description": "Summary text",
                "article_url": "https://example.com/article",
                "language": "en",
                "author": "Reporter",
                "publisher": {"name": "Example Media", "homepage_url": "https://example.com"},
                "tickers": ["NVDA", "AVGO"],
                "updated_utc": "2026-04-12T06:00:00Z",
            },
        }
        conn = FakeConn()

        pipeline._insert_news_rows(conn, None, [row])

        self.assertEqual(len(conn.calls), 1)
        sql, params = conn.calls[0]
        self.assertIn("ods.security_news_article_raw", sql)
        self.assertEqual(params[5], "Summary text")
        self.assertEqual(params[6], "https://example.com/article")
        self.assertEqual(params[7], "en")
        self.assertEqual(params[8], "Reporter")
        self.assertEqual(params[9], "Example Media")
        self.assertEqual(params[10], "https://example.com")
        self.assertEqual(params[11], "NVDA")

    def test_filing_upsert_backfills_accession_and_filing_date_from_minimal_row(self) -> None:
        row = {
            "filing_id": "NVDA-0001045810-26-000024",
            "symbol": "NVDA",
            "filing_type": "8-K",
            "filing_time": "2026-03-06T00:00:00Z",
            "title": "8-K",
            "source_vendor": "sec-edgar",
            "content": "<html>filing body</html>",
        }
        conn = FakeConn()

        pipeline._insert_filings_rows(conn, None, [row])

        self.assertEqual(len(conn.calls), 1)
        sql, params = conn.calls[0]
        self.assertIn("ods.sec_filing_document_raw", sql)
        self.assertEqual(params[0], "NVDA-0001045810-26-000024")
        self.assertEqual(params[3], "0001045810-26-000024")
        self.assertEqual(params[5], "2026-03-06")
        self.assertEqual(params[9], None)
        self.assertEqual(params[10], None)
        self.assertEqual(params[12], hashlib.sha256("<html>filing body</html>".encode("utf-8")).hexdigest())


if __name__ == "__main__":
    unittest.main()
