from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

import requests

from vnpy.web.contracts.tenx_hunter import (
    TenxFreshnessRow,
    TenxMarketSentimentMetricRow,
    TenxMarketSentimentPointRow,
    TenxMarketSentimentResponse,
    TenxMarketSentimentTone,
)


class MarketSentimentService:
    """Aggregate no-key public sentiment signals for the TenX US dashboard."""

    CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    CRYPTO_FNG_URL = "https://api.alternative.me/fng/?limit=7"

    def __init__(self, timeout: int = 8) -> None:
        self._timeout = timeout
        self._session = requests.Session()

    @staticmethod
    def _now_label() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def _iso_date_from_epoch_ms(value: float | int | str | None) -> str:
        if value in (None, ""):
            return ""
        try:
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            return str(value)

    @staticmethod
    def _iso_date_from_epoch(value: float | int | str | None) -> str:
        if value in (None, ""):
            return ""
        try:
            return datetime.fromtimestamp(float(value), timezone.utc).date().isoformat()
        except (TypeError, ValueError, OSError):
            return str(value)

    @staticmethod
    def _clamp(value: float, low: float = 0, high: float = 100) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _fmt_number(value: float | None, digits: int = 1) -> str:
        if value is None:
            return "N/A"
        return f"{value:.{digits}f}"

    @classmethod
    def _tone_from_score(cls, score: float | None) -> TenxMarketSentimentTone:
        if score is None:
            return "unavailable"
        if score < 25:
            return "extreme-fear"
        if score < 45:
            return "fear"
        if score < 55:
            return "neutral"
        if score < 75:
            return "greed"
        return "extreme-greed"

    @staticmethod
    def _rating_label(tone: str) -> str:
        return {
            "extreme-fear": "极度恐惧",
            "fear": "恐惧",
            "neutral": "中性",
            "greed": "贪婪",
            "extreme-greed": "极度贪婪",
            "unavailable": "不可用",
            "extreme fear": "极度恐惧",
            "fear": "恐惧",
            "neutral": "中性",
            "greed": "贪婪",
            "extreme greed": "极度贪婪",
        }.get(tone, tone)

    @staticmethod
    def _source_error_metric(key: str, label: str, source: str, source_url: str, detail: str) -> TenxMarketSentimentMetricRow:
        return TenxMarketSentimentMetricRow(
            key=key,
            label=label,
            category="source",
            display_value="N/A",
            tone="unavailable",
            status_label="不可用",
            detail=detail[:180],
            source=source,
            source_url=source_url,
            updated_at="",
        )

    def _get_json(self, url: str, *, headers: dict[str, str] | None = None, params: dict[str, str] | None = None) -> Any:
        response = self._session.get(url, headers=headers, params=params, timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def _load_cnn_fear_greed(self) -> TenxMarketSentimentMetricRow:
        headers = {
            "Accept": "application/json",
            "Origin": "https://www.cnn.com",
            "Referer": "https://www.cnn.com/markets/fear-and-greed",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        }
        payload = self._get_json(self.CNN_URL, headers=headers)
        current = payload.get("fear_and_greed") if isinstance(payload, dict) else {}
        score = float(current.get("score"))
        rating = str(current.get("rating") or "").lower()
        previous = current.get("previous_close")
        previous_value = float(previous) if previous is not None else None
        timestamp = str(current.get("timestamp") or "")
        history_data = (payload.get("fear_and_greed_historical") or {}).get("data") if isinstance(payload, dict) else []
        history = [
            TenxMarketSentimentPointRow(date=self._iso_date_from_epoch_ms(item.get("x")), value=round(float(item.get("y")), 2))
            for item in (history_data or [])[-30:]
            if item.get("x") is not None and item.get("y") is not None
        ]
        tone = self._tone_from_score(score)
        return TenxMarketSentimentMetricRow(
            key="cnn-fear-greed",
            label="CNN Fear & Greed",
            category="greed-index",
            value=round(score, 1),
            display_value=f"{score:.0f}",
            score=round(score, 1),
            tone=tone,
            status_label=self._rating_label(rating or tone),
            detail="股票市场七项情绪因子的综合温度计，越高代表越贪婪。",
            source="CNN",
            source_url="https://www.cnn.com/markets/fear-and-greed",
            updated_at=timestamp,
            previous_value=previous_value,
            change=round(score - previous_value, 2) if previous_value is not None else None,
            history=history,
        )

    def _load_yahoo_chart(self, symbol: str, *, range_: str = "1mo", interval: str = "1d") -> dict[str, Any]:
        return self._get_json(
            self.YAHOO_CHART_URL.format(symbol=symbol),
            params={"range": range_, "interval": interval},
            headers={"User-Agent": "Mozilla/5.0"},
        )

    @staticmethod
    def _chart_closes(payload: dict[str, Any]) -> tuple[list[float], list[int], dict[str, Any]]:
        result = payload["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        closes = [float(value) for value in quote.get("close", []) if value is not None]
        timestamps = [int(value) for value in result.get("timestamp", [])]
        return closes, timestamps, result.get("meta", {})

    def _load_vix(self) -> TenxMarketSentimentMetricRow:
        payload = self._load_yahoo_chart("%5EVIX", range_="1mo")
        closes, timestamps, meta = self._chart_closes(payload)
        latest = closes[-1]
        previous = closes[-2] if len(closes) >= 2 else None
        score = self._clamp(100 - (latest - 12) * 4.5)
        history = [
            TenxMarketSentimentPointRow(date=self._iso_date_from_epoch(ts), value=round(value, 2))
            for ts, value in zip(timestamps[-30:], closes[-30:])
        ]
        return TenxMarketSentimentMetricRow(
            key="vix",
            label="VIX 波动率",
            category="volatility",
            value=round(latest, 2),
            display_value=self._fmt_number(latest, 2),
            score=round(score, 1),
            tone=self._tone_from_score(score),
            status_label="低波动" if latest < 16 else "正常" if latest < 22 else "压力升高",
            detail="VIX 越低，通常代表市场越愿意承担风险；过低也意味着追高拥挤。",
            source="Yahoo Finance / Cboe",
            source_url="https://finance.yahoo.com/quote/%5EVIX/",
            updated_at=self._iso_date_from_epoch(meta.get("regularMarketTime") or (timestamps[-1] if timestamps else None)),
            previous_value=previous,
            change=round(latest - previous, 2) if previous is not None else None,
            history=history,
        )

    def _load_spy_trend(self) -> TenxMarketSentimentMetricRow:
        payload = self._load_yahoo_chart("SPY", range_="6mo")
        closes, timestamps, meta = self._chart_closes(payload)
        latest = closes[-1]
        ma20 = mean(closes[-20:]) if len(closes) >= 20 else latest
        ma125 = mean(closes[-125:]) if len(closes) >= 125 else mean(closes)
        distance_20 = (latest / ma20 - 1) * 100 if ma20 else 0
        distance_125 = (latest / ma125 - 1) * 100 if ma125 else 0
        score = self._clamp(50 + distance_20 * 2 + distance_125 * 2.2)
        history = [
            TenxMarketSentimentPointRow(date=self._iso_date_from_epoch(ts), value=round(value, 2))
            for ts, value in zip(timestamps[-30:], closes[-30:])
        ]
        return TenxMarketSentimentMetricRow(
            key="spy-trend",
            label="SPY 趋势位置",
            category="trend",
            value=round(distance_125, 2),
            display_value=f"{distance_125:+.1f}%",
            score=round(score, 1),
            tone=self._tone_from_score(score),
            status_label="高于中期均线" if distance_125 > 0 else "低于中期均线",
            detail=f"SPY 相对 125 日均线 {distance_125:+.1f}%，相对 20 日均线 {distance_20:+.1f}%。",
            source="Yahoo Finance",
            source_url="https://finance.yahoo.com/quote/SPY/",
            updated_at=self._iso_date_from_epoch(meta.get("regularMarketTime") or (timestamps[-1] if timestamps else None)),
            previous_value=None,
            change=round(distance_20, 2),
            history=history,
        )

    def _load_high_yield_spread(self) -> TenxMarketSentimentMetricRow:
        payload = self._load_yahoo_chart("HYG", range_="3mo")
        closes, timestamps, meta = self._chart_closes(payload)
        latest = closes[-1]
        previous_value = closes[-2] if len(closes) >= 2 else None
        low = min(closes)
        high = max(closes)
        percentile = ((latest - low) / max(0.01, high - low)) * 100
        ma20 = mean(closes[-20:]) if len(closes) >= 20 else latest
        distance_20 = (latest / ma20 - 1) * 100 if ma20 else 0
        score = self._clamp(30 + percentile * 0.55 + distance_20 * 6)
        history = [
            TenxMarketSentimentPointRow(date=self._iso_date_from_epoch(ts), value=round(value, 2))
            for ts, value in zip(timestamps[-30:], closes[-30:])
        ]
        return TenxMarketSentimentMetricRow(
            key="hyg-credit",
            label="HYG 信用风险偏好",
            category="credit",
            value=round(percentile, 2),
            display_value=f"{percentile:.0f}%",
            score=round(score, 1),
            tone=self._tone_from_score(score),
            status_label="信用偏强" if percentile >= 65 else "信用中性" if percentile >= 35 else "信用转弱",
            detail=f"HYG 处在近 3 个月区间的 {percentile:.0f}% 分位，相对 20 日均线 {distance_20:+.1f}%。",
            source="Yahoo Finance / HYG",
            source_url="https://finance.yahoo.com/quote/HYG/",
            updated_at=self._iso_date_from_epoch(meta.get("regularMarketTime") or (timestamps[-1] if timestamps else None)),
            previous_value=previous_value,
            change=round(latest - previous_value, 2) if previous_value is not None else None,
            history=history,
        )

    def _load_crypto_fear_greed(self) -> TenxMarketSentimentMetricRow:
        payload = self._get_json(self.CRYPTO_FNG_URL, headers={"User-Agent": "Mozilla/5.0"})
        items = payload.get("data") if isinstance(payload, dict) else []
        current = items[0]
        value = float(current["value"])
        previous_value = float(items[1]["value"]) if len(items) >= 2 else None
        history = [
            TenxMarketSentimentPointRow(date=self._iso_date_from_epoch(item.get("timestamp")), value=float(item["value"]))
            for item in reversed(items)
        ]
        tone = self._tone_from_score(value)
        return TenxMarketSentimentMetricRow(
            key="crypto-fear-greed",
            label="Crypto Fear & Greed",
            category="cross-asset",
            value=round(value, 1),
            display_value=f"{value:.0f}",
            score=round(value, 1),
            tone=tone,
            status_label=self._rating_label(str(current.get("value_classification") or "").lower()),
            detail="跨市场投机情绪参考，不直接代表美股，但可辅助判断风险偏好是否分裂。",
            source="Alternative.me",
            source_url="https://alternative.me/crypto/fear-and-greed-index/",
            updated_at=self._iso_date_from_epoch(current.get("timestamp")),
            previous_value=previous_value,
            change=round(value - previous_value, 2) if previous_value is not None else None,
            history=history,
        )

    def _metric_loaders(self):
        return [
            ("cnn-fear-greed", "CNN Fear & Greed", "CNN", "https://www.cnn.com/markets/fear-and-greed", self._load_cnn_fear_greed),
            ("vix", "VIX 波动率", "Yahoo Finance / Cboe", "https://finance.yahoo.com/quote/%5EVIX/", self._load_vix),
            ("spy-trend", "SPY 趋势位置", "Yahoo Finance", "https://finance.yahoo.com/quote/SPY/", self._load_spy_trend),
            ("hyg-credit", "HYG 信用风险偏好", "Yahoo Finance / HYG", "https://finance.yahoo.com/quote/HYG/", self._load_high_yield_spread),
            ("crypto-fear-greed", "Crypto Fear & Greed", "Alternative.me", "https://alternative.me/crypto/fear-and-greed-index/", self._load_crypto_fear_greed),
        ]

    @classmethod
    def _regime_summary(cls, score: float | None, metrics: list[TenxMarketSentimentMetricRow]) -> tuple[TenxMarketSentimentTone, str, str, str]:
        if score is None:
            return "unavailable", "数据不可用", "情绪源暂时不可用，不能形成仓位判断。", "先检查数据源，再做仓位动作。"

        regime = cls._tone_from_score(score)
        label = cls._rating_label(regime)
        cnn = next((metric for metric in metrics if metric.key == "cnn-fear-greed" and metric.value is not None), None)
        vix = next((metric for metric in metrics if metric.key == "vix" and metric.value is not None), None)
        core = f"综合情绪 {score:.0f}/100，处于{label}区间。"
        if cnn:
            core += f" CNN 贪婪指数 {cnn.display_value}。"
        if vix:
            core += f" VIX {vix.display_value}。"

        posture = {
            "extreme-greed": "情绪过热，适合降低追高冲动，优先检查仓位上限和回撤条件。",
            "greed": "风险偏好偏强，继续跟踪主线，但新仓需要更严格的事件验证。",
            "neutral": "情绪中性，按个股事件和结构信号分层处理。",
            "fear": "情绪偏弱，适合寻找错杀和反转确认，不急于满仓。",
            "extreme-fear": "极度恐惧，先看流动性和信用压力，再找逆向机会。",
            "unavailable": "数据不可用，暂停情绪判断。",
        }[regime]
        return regime, label, core, posture

    def get_snapshot(self, market: str = "US") -> TenxMarketSentimentResponse:
        normalized_market = "US" if (market or "US").upper() == "US" else "CN"
        metrics: list[TenxMarketSentimentMetricRow] = []
        notes: list[str] = []

        for key, label, source, source_url, loader in self._metric_loaders():
            try:
                metrics.append(loader())
            except Exception as exc:  # noqa: BLE001 - one source should not break the dashboard
                metrics.append(self._source_error_metric(key, label, source, source_url, f"{source} 数据暂时拉取失败：{exc}"))
                notes.append(f"{label} 拉取失败：{exc}")

        available_scores = [metric.score for metric in metrics if metric.score is not None]
        composite = round(mean(available_scores), 1) if available_scores else None
        regime, regime_label, summary, posture = self._regime_summary(composite, metrics)
        available_count = len(available_scores)
        data_quality = f"{available_count}/{len(metrics)} sources available"
        snapshot_at = self._now_label()

        return TenxMarketSentimentResponse(
            market=normalized_market,
            snapshot_at=snapshot_at,
            composite_score=composite,
            regime=regime,
            regime_label=regime_label,
            summary=summary,
            risk_posture=posture,
            data_quality=data_quality,
            freshness=TenxFreshnessRow(
                updated_at=snapshot_at,
                data_complete=available_count == len(metrics),
                source_summary="CNN / Yahoo Finance / Alternative.me",
                coverage="Fear & Greed、VIX、SPY 趋势、HYG 信用风险偏好、Crypto Fear & Greed",
            ),
            metrics=metrics,
            notes=notes,
        )
