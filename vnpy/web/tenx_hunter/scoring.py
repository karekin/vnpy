from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TenxStage = Literal["early", "validation", "acceleration", "crowded"]


@dataclass(frozen=True)
class ScoreComponents:
    growth: float
    quality: float
    momentum: float
    valuation: float
    size: float
    evidence: float
    theme: float
    risk: float

    @property
    def total(self) -> float:
        return round(
            self.growth * 0.22
            + self.quality * 0.16
            + self.valuation * 0.14
            + self.size * 0.12
            + self.evidence * 0.12
            + self.theme * 0.06
            + self.momentum * 0.08
            + self.risk * 0.10,
            2,
        )


@dataclass(frozen=True)
class CandidateExplanation:
    selection_reason: str
    stage_reason: str
    crowding_note: str
    score_drivers: list[str]


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return round(max(lower, min(upper, value)), 2)


def _as_percent(value: float | None) -> float:
    if value is None:
        return 0.0
    if -1.0 <= value <= 1.0:
        return value * 100
    return value


def _as_billions(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 1_000_000_000


def _fmt_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{_as_percent(value):.1f}%"


def _fmt_billions(value: float | None) -> str:
    billions = _as_billions(value)
    if billions is None:
        return "N/A"
    if billions >= 1000:
        return f"${billions / 1000:.1f}T"
    return f"${billions:.0f}B"


def growth_score(revenue_yoy: float | None) -> float:
    pct = _as_percent(revenue_yoy)
    return _clamp(30 + pct * 1.15)


def quality_score(op_margin: float | None, fcf_margin: float | None) -> float:
    op_pct = _as_percent(op_margin)
    fcf_pct = _as_percent(fcf_margin)
    return _clamp(35 + op_pct * 0.9 + fcf_pct * 0.7)


def momentum_score(return_5d: float | None, distance_from_high: float | None) -> float:
    ret_pct = _as_percent(return_5d)
    distance_pct = _as_percent(distance_from_high) if distance_from_high is not None else -8.0

    score = 50.0
    if ret_pct >= 0:
        score += min(ret_pct * 2.2, 18.0)
    else:
        score += max(ret_pct * 2.5, -25.0)

    if distance_pct >= -2:
        score -= 12
    elif distance_pct >= -12:
        score += 10
    elif distance_pct >= -25:
        score += 4
    else:
        score -= 6
    return _clamp(score)


def valuation_score(ps_ttm: float | None) -> float:
    if ps_ttm is None:
        return 55.0
    ps = max(ps_ttm, 0.0)
    if ps <= 2:
        return 95.0
    if ps <= 4:
        return _clamp(95 - (ps - 2) * 10)
    if ps <= 8:
        return _clamp(75 - (ps - 4) * 6.25)
    if ps <= 12:
        return _clamp(50 - (ps - 8) * 5)
    if ps <= 20:
        return _clamp(30 - (ps - 12) * 2.5)
    return _clamp(10 - (ps - 20) * 1.5)


def size_score(market_cap: float | None) -> float:
    billions = _as_billions(market_cap)
    if billions is None:
        return 50.0
    if billions < 1:
        return 25.0
    if billions < 3:
        return _clamp(45 + (billions - 1) * 15)
    if billions < 10:
        return _clamp(75 + (billions - 3) * 3)
    if billions < 25:
        return _clamp(96 - (billions - 10) * 1.2)
    if billions < 60:
        return _clamp(78 - (billions - 25) * 0.8)
    if billions < 120:
        return _clamp(50 - (billions - 60) * 0.4)
    if billions < 250:
        return _clamp(26 - (billions - 120) * 0.1)
    return _clamp(12 - (billions - 250) * 0.02)


def evidence_score(theme_count: int, positive_signal_count: int, negative_event_count: int) -> float:
    return _clamp(20 + theme_count * 10 + positive_signal_count * 12 - max(negative_event_count - 1, 0) * 4)


def theme_score(theme_count: int) -> float:
    return _clamp(35 + theme_count * 18)


def risk_score(risk_count: int, negative_event_count: int) -> float:
    return _clamp(100 - risk_count * 14 - negative_event_count * 12)


def build_score_components(
    revenue_yoy: float | None,
    op_margin: float | None,
    fcf_margin: float | None,
    return_5d: float | None,
    distance_from_high: float | None,
    ps_ttm: float | None,
    market_cap: float | None,
    risk_count: int,
    negative_event_count: int,
    theme_count: int,
    positive_signal_count: int,
) -> ScoreComponents:
    return ScoreComponents(
        growth=growth_score(revenue_yoy),
        quality=quality_score(op_margin, fcf_margin),
        momentum=momentum_score(return_5d, distance_from_high),
        valuation=valuation_score(ps_ttm),
        size=size_score(market_cap),
        evidence=evidence_score(theme_count, positive_signal_count, negative_event_count),
        theme=theme_score(theme_count),
        risk=risk_score(risk_count, negative_event_count),
    )


def classify_stage(
    components: ScoreComponents,
    *,
    ps_ttm: float | None,
    market_cap: float | None,
    return_5d: float | None,
    distance_from_high: float | None,
) -> TenxStage:
    billions = _as_billions(market_cap)
    ret_5d_pct = _as_percent(return_5d)
    distance_pct = _as_percent(distance_from_high) if distance_from_high is not None else -12.0

    crowded_by_scale = billions is not None and billions >= 150 and components.valuation <= 35
    crowded_by_valuation = ps_ttm is not None and ps_ttm >= 18 and distance_pct >= -8
    crowded_by_extension = ret_5d_pct >= 15 and distance_pct >= -2
    if crowded_by_scale or crowded_by_valuation or crowded_by_extension:
        return "crowded"

    if (
        components.growth >= 70
        and components.quality >= 55
        and components.evidence >= 60
        and components.valuation >= 35
        and components.risk >= 35
    ):
        return "acceleration"

    if (
        components.growth >= 52
        and components.evidence >= 35
        and components.valuation >= 25
        and components.risk >= 20
    ):
        return "validation"

    return "early"


def explain_components(components: ScoreComponents) -> str:
    top = sorted(
        {
            "增长": components.growth,
            "质量": components.quality,
            "估值": components.valuation,
            "市值弹性": components.size,
            "证据": components.evidence,
            "主题": components.theme,
            "动量": components.momentum,
            "风险": components.risk,
        }.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    return "、".join(f"{label}{score:.1f}" for label, score in top)


def build_score_driver_notes(
    components: ScoreComponents,
    *,
    ps_ttm: float | None,
    market_cap: float | None,
    return_5d: float | None,
    distance_from_high: float | None,
) -> list[str]:
    drivers: list[tuple[str, float, str]] = [
        ("增长", components.growth, f"增长分 {components.growth:.0f}，代表收入扩张仍在兑现。"),
        ("质量", components.quality, f"质量分 {components.quality:.0f}，利润率 / FCF 质量在可用区间。"),
        ("估值", components.valuation, f"估值分 {components.valuation:.0f}，当前 P/S 约 {ps_ttm:.1f}x。" if ps_ttm is not None else f"估值分 {components.valuation:.0f}，当前估值口径暂缺。"),
        ("市值弹性", components.size, f"市值弹性分 {components.size:.0f}，当前市值约 {_fmt_billions(market_cap)}。"),
        ("证据", components.evidence, f"证据分 {components.evidence:.0f}，说明主题与正向验证在累积。"),
        ("主题", components.theme, f"主题分 {components.theme:.0f}，说明公司与当前主线相关性较高。"),
        ("动量", components.momentum, f"动量分 {components.momentum:.0f}，近 5 日 {_fmt_percent(return_5d)}，距离近期高点 {_fmt_percent(distance_from_high)}。"),
        ("风险", components.risk, f"风险分 {components.risk:.0f}，说明负面事件与风险标签仍可控。"),
    ]
    return [note for _label, _score, note in sorted(drivers, key=lambda item: item[1], reverse=True)[:3]]


def build_candidate_explanation(
    stage: TenxStage,
    components: ScoreComponents,
    *,
    ps_ttm: float | None,
    market_cap: float | None,
    return_5d: float | None,
    distance_from_high: float | None,
) -> CandidateExplanation:
    if stage == "crowded":
        selection_reason = "默认不进主候选池：逻辑可能依然成立，但赔率已经被高估值 / 大市值 / 贴近新高的拥挤交易压缩。"
        stage_reason = (
            f"被判为 crowded，因为当前 P/S {ps_ttm:.1f}x、"
            f"市值 {_fmt_billions(market_cap)}、距离近期高点 {_fmt_percent(distance_from_high)}，更像高位热门股而不是赔率更优的主狩猎对象。"
            if ps_ttm is not None
            else "被判为 crowded，因为当前价格位置与体量更接近高位拥挤交易。"
        )
        crowding_note = "系统宁可把它放到观察或对照组，也不默认在赔率被压扁后继续追热度。"
    elif stage == "acceleration":
        selection_reason = "进入主候选池，因为成长、质量与证据同时强化，且还没被拥挤交易完全挤压。"
        stage_reason = "被判为 acceleration，因为财务兑现、证据验证和中短期 setup 同步转强。"
        crowding_note = "虽然热度可能已经上来，但目前估值 / 市值 / 高位程度还没触发 crowded 阈值。"
    elif stage == "validation":
        selection_reason = "进入主候选池，因为基本面和证据已经形成验证，赔率通常比最热门 megacap 更平衡。"
        stage_reason = "被判为 validation，因为成长逻辑已开始被财务和事件同时验证，但还没有进入全面加速或高位拥挤。"
        crowding_note = "当前仍处于可研究、可跟踪的赔率区间，不是典型追热交易。"
    else:
        selection_reason = "进入主候选池，因为逻辑刚开始被验证，仍处于值得提前研究的位置。"
        stage_reason = "被判为 early，因为成长方向已经出现，但验证证据和盈利质量还在继续累积。"
        crowding_note = "它不是最热的名字，反而意味着如果后续验证继续增强，赔率可能更大。"

    return CandidateExplanation(
        selection_reason=selection_reason,
        stage_reason=stage_reason,
        crowding_note=crowding_note,
        score_drivers=build_score_driver_notes(
            components,
            ps_ttm=ps_ttm,
            market_cap=market_cap,
            return_5d=return_5d,
            distance_from_high=distance_from_high,
        ),
    )
