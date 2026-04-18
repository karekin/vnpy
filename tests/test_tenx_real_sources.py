from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.web.tenx_hunter.real_sources import (
    SEC_ARCHIVES_URL,
    build_filings_from_submissions,
    build_institutional_activity_from_submissions,
    fetch_sec_13f_information_table,
    fetch_yfinance_bundle,
)


class RealSourcesTests(unittest.TestCase):
    @patch("vnpy.web.tenx_hunter.real_sources.request_text")
    @patch("vnpy.web.tenx_hunter.real_sources.fetch_sec_filing_index")
    def test_fetch_sec_13f_information_table_parses_xml_holdings(self, mocked_index, mocked_text) -> None:
        mocked_index.return_value = {
            "directory": {
                "item": [
                    {"name": "primary_doc.xml"},
                    {"name": "information_table.xml"},
                ]
            }
        }
        mocked_text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
  <infoTable>
    <nameOfIssuer>INTEL CORP</nameOfIssuer>
    <titleOfClass>COM</titleOfClass>
    <cusip>458140100</cusip>
    <value>7925257721</value>
    <shrsOrPrnAmt>
      <sshPrnamt>214776632</sshPrnamt>
      <sshPrnamtType>SH</sshPrnamtType>
    </shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
  </infoTable>
</informationTable>
"""

        document, holdings = fetch_sec_13f_information_table("1045810", "0001045810-26-000011", "test-agent")

        self.assertEqual(document, "information_table.xml")
        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0]["nameOfIssuer"], "INTEL CORP")
        self.assertEqual(holdings[0]["sshPrnamt"], "214776632")

    @patch("vnpy.web.tenx_hunter.real_sources.fetch_sec_filing_document", return_value="<html>filing body</html>")
    def test_build_filings_from_submissions_keeps_structured_metadata(self, mocked_fetch) -> None:
        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0001045810-26-000024"],
                    "form": ["8-K"],
                    "filingDate": ["2026-03-06"],
                    "reportDate": ["2026-03-02"],
                    "acceptanceDateTime": ["2026-03-06T13:01:02.000Z"],
                    "primaryDocument": ["d930164d8k.htm"],
                    "primaryDocDescription": ["8-K"],
                    "isXBRL": [1],
                    "isInlineXBRL": [1],
                }
            }
        }

        records = build_filings_from_submissions("NVDA", "1045810", submissions, "test-agent", limit=2)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.filing_id, "NVDA-0001045810-26-000024")
        self.assertEqual(record.symbol, "NVDA")
        self.assertEqual(record.cik, "1045810")
        self.assertEqual(record.accession_number, "0001045810-26-000024")
        self.assertEqual(record.filing_type, "8-K")
        self.assertEqual(record.filing_date, "2026-03-06")
        self.assertEqual(record.filing_time, "2026-03-06T13:01:02Z")
        self.assertEqual(record.report_period, "2026-03-02")
        self.assertEqual(record.primary_document, "d930164d8k.htm")
        self.assertEqual(
            record.filing_url,
            SEC_ARCHIVES_URL.format(
                cik="1045810",
                accession="000104581026000024",
                document="d930164d8k.htm",
            ),
        )
        self.assertEqual(record.raw_payload["acceptanceDateTime"], "2026-03-06T13:01:02.000Z")
        self.assertEqual(record.raw_payload["reportDate"], "2026-03-02")
        self.assertTrue(record.raw_payload["isInlineXBRL"])
        mocked_fetch.assert_called_once()

    @patch("vnpy.web.tenx_hunter.real_sources.request_json")
    def test_fetch_yfinance_bundle_should_tolerate_quote_and_summary_auth_failures(self, mocked_request_json) -> None:
        def _fake_request(url: str, *args, **kwargs):
            if "finance/quote" in url or "quoteSummary" in url:
                raise RuntimeError("401 Unauthorized")
            if "finance/chart" in url:
                return {
                    "chart": {
                        "result": [
                            {
                                "meta": {
                                    "currency": "USD",
                                    "exchangeName": "NMS",
                                },
                                "timestamp": [1711929600],
                                "indicators": {
                                    "quote": [
                                        {
                                            "open": [100.0],
                                            "high": [110.0],
                                            "low": [99.0],
                                            "close": [108.0],
                                            "volume": [123456],
                                        }
                                    ],
                                    "adjclose": [
                                        {
                                            "adjclose": [108.0],
                                        }
                                    ],
                                },
                            }
                        ]
                    }
                }
            if "finance/search" in url:
                return {
                    "quotes": [
                        {
                            "symbol": "NVDA",
                            "longname": "NVIDIA Corp.",
                            "shortname": "NVIDIA",
                            "exchDisp": "NASDAQ",
                        }
                    ],
                    "news": [
                        {
                            "uuid": "news-1",
                            "title": "NVIDIA AI update",
                            "summary": "Demand stays strong.",
                            "providerPublishTime": 1711933200,
                            "publisher": "Yahoo Finance",
                            "link": "https://example.com/nvda-news",
                        }
                    ],
                }
            raise AssertionError(f"unexpected url: {url}")

        mocked_request_json.side_effect = _fake_request

        securities, prices, news_items = fetch_yfinance_bundle(["NVDA"], "2026-04-01", "2026-04-11")

        self.assertEqual(len(securities), 1)
        self.assertEqual(securities[0].symbol, "NVDA")
        self.assertEqual(securities[0].company_name, "NVIDIA Corp.")
        self.assertEqual(securities[0].exchange_name, "NMS")
        self.assertEqual(securities[0].currency, "USD")
        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0].close, 108.0)
        self.assertEqual(len(news_items), 1)
        self.assertEqual(news_items[0].symbol, "NVDA")

    @patch("vnpy.web.tenx_hunter.real_sources.fetch_sec_13f_information_table")
    def test_build_institutional_activity_from_submissions_maps_held_symbol_into_universe(self, mocked_table) -> None:
        mocked_table.return_value = (
            "information_table.xml",
            [
                {
                    "nameOfIssuer": "INTEL CORP",
                    "titleOfClass": "COM",
                    "value": "7925257721",
                    "sshPrnamt": "214776632",
                    "sshPrnamtType": "SH",
                }
            ],
        )
        submissions = {
            "filings": {
                "recent": {
                    "accessionNumber": ["0001045810-26-000011"],
                    "form": ["13F-HR"],
                    "filingDate": ["2026-02-17"],
                    "reportDate": ["2025-12-31"],
                    "acceptanceDateTime": ["2026-02-17T16:27:55.000Z"],
                }
            }
        }

        records = build_institutional_activity_from_submissions(
            manager_symbol="NVDA",
            manager_name="NVIDIA CORP",
            manager_cik="1045810",
            submissions=submissions,
            title_to_ticker={"INTEL CORP": "INTC", "INTEL": "INTC"},
            universe_symbols={"INTC", "NVDA"},
            user_agent="test-agent",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.symbol, "INTC")
        self.assertEqual(record.manager_symbol, "NVDA")
        self.assertEqual(record.filing_type, "13F-HR")
        self.assertEqual(record.position_value_usd, 7925257721.0)
        self.assertIn("INTC", record.content)


if __name__ == "__main__":
    unittest.main()
