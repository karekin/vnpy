from vnpy.web.contracts.tenx_hunter import TenxMarketSentimentMetricRow
from vnpy.web.services.market_sentiment_service import MarketSentimentService


def metric(key: str, score: float) -> TenxMarketSentimentMetricRow:
    return TenxMarketSentimentMetricRow(
        key=key,
        label=key,
        category="test",
        value=score,
        display_value=str(score),
        score=score,
        tone=MarketSentimentService._tone_from_score(score),
        status_label="test",
        detail="test metric",
        source="test",
        source_url="https://example.com",
        updated_at="2026-05-31",
    )


def test_market_sentiment_snapshot_combines_available_scores(monkeypatch) -> None:
    service = MarketSentimentService()
    monkeypatch.setattr(service, "_load_cnn_fear_greed", lambda: metric("cnn-fear-greed", 60))
    monkeypatch.setattr(service, "_load_vix", lambda: metric("vix", 80))
    monkeypatch.setattr(service, "_load_spy_trend", lambda: metric("spy-trend", 70))
    monkeypatch.setattr(service, "_load_high_yield_spread", lambda: metric("high-yield-spread", 75))
    monkeypatch.setattr(service, "_load_crypto_fear_greed", lambda: metric("crypto-fear-greed", 30))

    snapshot = service.get_snapshot("US")

    assert snapshot.market == "US"
    assert snapshot.composite_score == 63
    assert snapshot.regime == "greed"
    assert snapshot.data_quality == "5/5 sources available"


def test_market_sentiment_snapshot_keeps_partial_data(monkeypatch) -> None:
    service = MarketSentimentService()
    monkeypatch.setattr(service, "_load_cnn_fear_greed", lambda: metric("cnn-fear-greed", 60))
    monkeypatch.setattr(service, "_load_vix", lambda: metric("vix", 80))
    monkeypatch.setattr(service, "_load_spy_trend", lambda: metric("spy-trend", 70))
    monkeypatch.setattr(service, "_load_high_yield_spread", lambda: metric("high-yield-spread", 75))

    def fail_crypto():
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(service, "_load_crypto_fear_greed", fail_crypto)

    snapshot = service.get_snapshot("US")

    assert snapshot.composite_score == 71.2
    assert snapshot.data_quality == "4/5 sources available"
    assert snapshot.metrics[-1].tone == "unavailable"
    assert snapshot.notes
