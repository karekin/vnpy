from vnpy.web.services.political_signal_service import PoliticalSignalService


def test_political_signal_snapshot_parses_open_cabinet_html(monkeypatch) -> None:
    html = """
    <html><body>
      <p>President Donald J. Trump's most recent periodic transaction report discloses 5,011 individual securities trades between January 2025 and March 2026 — the largest record. Roughly 93 percent of the trades (4,656 of 5,011) were reported to OGE more than 30 days after they occurred — the threshold federal law sets for late disclosure under the STOCK Act.</p>
      <p>5011 trades 1298 sales 3713 purchases 4656 late filings (93%)</p>
      <p>Last filing: May 14, 2026|Transactions: Jan 1, 2025 – Mar 30, 2026</p>
      <table>
        <tr><th>Date</th><th>Description</th><th>Ticker</th><th>Type</th><th>Amount</th><th>Source</th></tr>
        <tr><td>Mar 30, 2026</td><td>ACME CORP Late</td><td>ACME</td><td>Purchase</td><td>$15K-$50K</td><td><a href="https://example.com/report.pdf">PDF</a></td></tr>
      </table>
    </body></html>
    """
    service = PoliticalSignalService()
    monkeypatch.setattr(service, "_load_open_cabinet_html", lambda: html)

    snapshot = service.get_snapshot("US")

    assert snapshot.market == "US"
    assert snapshot.disclosure.latest_filing_date == "May 14, 2026"
    assert snapshot.disclosure.total_trades == 5011
    assert snapshot.disclosure.late_filing_pct == 92.9
    assert snapshot.recent_trades[0].symbol == "ACME"
    assert snapshot.recent_trades[0].is_late is True
    assert any(item.symbol == "IBM" and item.evidence_grade == "D" for item in snapshot.mentions)
