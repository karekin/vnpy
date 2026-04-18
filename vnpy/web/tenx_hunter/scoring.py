from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TenxMarket = Literal["CN", "US"]
TenxStage = Literal["discovery", "validation", "acceleration", "crowded", "falsified"]


@dataclass(frozen=True)
class ScoreProfile:
    market: TenxMarket
    weights: dict[str, int]


US_SCORE_PROFILE = ScoreProfile(
    market="US",
    weights={
        "growth": 22,
        "quality": 16,
        "valuation": 14,
        "size": 12,
        "evidence": 12,
        "theme": 6,
        "momentum": 8,
        "risk": 10,
    },
)

CN_SCORE_PROFILE = ScoreProfile(
    market="CN",
    weights={
        "industry_prosperity": 25,
        "leader_position": 20,
        "financial_acceleration": 25,
        "cashflow_quality": 15,
        "moat": 10,
        "valuation_chip": 5,
    },
)


@dataclass(frozen=True)
class ScoreComponents:
    growth: float = 0.0
    quality: float = 0.0
    momentum: float = 0.0
    valuation: float = 0.0
    size: float = 0.0
    evidence: float = 0.0
    theme: float = 0.0
    risk: float = 0.0
    industry_prosperity: float = 0.0
    leader_position: float = 0.0
    financial_acceleration: float = 0.0
    cashflow_quality: float = 0.0
    moat: float = 0.0
    valuation_chip: float = 0.0
    profile: ScoreProfile = US_SCORE_PROFILE

    @property
    def total(self) -> float:
        weighted_total = 0.0
        for key, weight in self.profile.weights.items():
            weighted_total += getattr(self, key) * (weight / 100)
        return round(weighted_total, 2)


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


def _fmt_billions(value: float | None, *, currency: str = "$") -> str:
    billions = _as_billions(value)
    if billions is None:
        return "N/A"
    if billions >= 1000:
        return f"{currency}{billions / 1000:.1f}T"
    return f"{currency}{billions:.0f}B"


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


def industry_prosperity_score(theme_count: int, positive_signal_count: int) -> float:
    return _clamp(40 + theme_count * 16 + positive_signal_count * 6)


def leader_position_score(market_cap: float | None, return_5d: float | None) -> float:
    billions = _as_billions(market_cap)
    ret = _as_percent(return_5d)
    if billions is None:
        return _clamp(55 + min(max(ret, -10), 10))
    if billions < 5:
        base = 42
    elif billions < 20:
        base = 70
    elif billions < 80:
        base = 84
    elif billions < 300:
        base = 65
    else:
        base = 48
    return _clamp(base + min(max(ret * 0.6, -8), 8))


def financial_acceleration_score(revenue_yoy: float | None, netprofit_yoy: float | None) -> float:
    rev_pct = _as_percent(revenue_yoy)
    profit_pct = _as_percent(netprofit_yoy)
    return _clamp(28 + rev_pct * 0.6 + profit_pct * 0.45)


def cashflow_quality_score(fcf_margin: float | None, cfo_to_np: float | None) -> float:
    fcf_pct = _as_percent(fcf_margin)
    cfo_ratio = cfo_to_np if cfo_to_np is not None else 0.8
    return _clamp(38 + fcf_pct * 0.9 + cfo_ratio * 18)


def moat_score(rd_ratio_ttm: float | None) -> float:
    rd_pct = _as_percent(rd_ratio_ttm)
    return _clamp(35 + rd_pct * 2.8)


def valuation_chip_score(pe_ttm: float | None, pb: float | None, turnover_rate: float | None) -> float:
    pe_component = 70.0
    if pe_ttm is not None:
        if pe_ttm <= 0:
            pe_component = 20.0
        elif pe_ttm <= 20:
            pe_component = 85.0
        elif pe_ttm <= 35:
            pe_component = _clamp(85 - (pe_ttm - 20) * 2.2)
        elif pe_ttm <= 60:
            pe_component = _clamp(52 - (pe_ttm - 35) * 1.2)
        else:
            pe_component = _clamp(25 - (pe_ttm - 60) * 0.25)

    pb_component = 72.0
    if pb is not None:
        if pb <= 1.5:
            pb_component = 88.0
        elif pb <= 4:
            pb_component = _clamp(88 - (pb - 1.5) * 10)
        elif pb <= 8:
            pb_component = _clamp(63 - (pb - 4) * 6.5)
        else:
            pb_component = _clamp(30 - (pb - 8) * 2)

    turnover_component = 70.0
    if turnover_rate is not None:
        turnover_pct = _as_percent(turnover_rate)
        if turnover_pct <= 2.5:
            turnover_component = 82.0
        elif turnover_pct <= 8:
            turnover_component = _clamp(82 - (turnover_pct - 2.5) * 6)
        else:
            turnover_component = _clamp(48 - (turnover_pct - 8) * 2.2)

    return _clamp(pe_component * 0.5 + pb_component * 0.35 + turnover_component * 0.15)


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
    *,
    market: TenxMarket = "US",
    netprofit_yoy: float | None = None,
    cfo_to_np: float | None = None,
    rd_ratio_ttm: float | None = None,
    pe_ttm: float | None = None,
    pb: float | None = None,
    turnover_rate: float | None = None,
) -> ScoreComponents:
    if market == "CN":
        return ScoreComponents(
            industry_prosperity=industry_prosperity_score(theme_count, positive_signal_count),
            leader_position=leader_position_score(market_cap, return_5d),
            financial_acceleration=financial_acceleration_score(revenue_yoy, netprofit_yoy),
            cashflow_quality=cashflow_quality_score(fcf_margin, cfo_to_np),
            moat=moat_score(rd_ratio_ttm),
            valuation_chip=valuation_chip_score(pe_ttm, pb, turnover_rate),
            profile=CN_SCORE_PROFILE,
        )

    return ScoreComponents(
        growth=growth_score(revenue_yoy),
        quality=quality_score(op_margin, fcf_margin),
        momentum=momentum_score(return_5d, distance_from_high),
        valuation=valuation_score(ps_ttm),
        size=size_score(market_cap),
        evidence=evidence_score(theme_count, positive_signal_count, negative_event_count),
        theme=theme_score(theme_count),
        risk=risk_score(risk_count, negative_event_count),
        profile=US_SCORE_PROFILE,
    )


def classify_stage(
    components: ScoreComponents,
    *,
    market: TenxMarket = "US",
    ps_ttm: float | None = None,
    market_cap: float | None = None,
    return_5d: float | None = None,
    distance_from_high: float | None = None,
    risk_count: int = 0,
    negative_event_count: int = 0,
) -> TenxStage:
    if market == "CN":
        if risk_count >= 3 or negative_event_count >= 3:
            return "falsified"
        if components.valuation_chip <= 35 and components.financial_acceleration >= 65:
            return "crowded"
        if components.financial_acceleration >= 72 and components.cashflow_quality >= 60 and components.industry_prosperity >= 58:
            return "acceleration"
        if components.financial_acceleration >= 52 and components.industry_prosperity >= 48:
            return "validation"
        return "discovery"

    billions = _as_billions(market_cap)
    ret_5d_pct = _as_percent(return_5d)
    distance_pct = _as_percent(distance_from_high) if distance_from_high is not None else -12.0

    crowded_by_scale = billions is not None and billions >= 150 and components.valuation <= 35
    crowded_by_valuation = ps_ttm is not None and ps_ttm >= 18 and distance_pct >= -8
    crowded_by_extension = ret_5d_pct >= 15 and distance_pct >= -2
    if risk_count >= 4 or negative_event_count >= 4:
        return "falsified"
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
    return "discovery"


def explain_components(components: ScoreComponents, *, market: TenxMarket = "US") -> str:
    if market == "CN":
        top = sorted(
            {
                "行业景气": components.industry_prosperity,
                "龙头位置": components.leader_position,
                "财务加速": components.financial_acceleration,
                "现金流质量": components.cashflow_quality,
                "研发护城河": components.moat,
                "估值筹码": components.valuation_chip,
            }.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        return "、".join(f"{label}{score:.1f}" for label, score in top)

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
    market: TenxMarket = "US",
    ps_ttm: float | None = None,
    pe_ttm: float | None = None,
    pb: float | None = None,
    market_cap: float | None = None,
    return_5d: float | None = None,
    distance_from_high: float | None = None,
) -> list[str]:
    if market == "CN":
        pe_text = f"{pe_ttm:.1f}" if pe_ttm is not None else "N/A"
        pb_text = f"{pb:.1f}" if pb is not None else "N/A"
        drivers: list[tuple[str, float, str]] = [
            ("行业景气", components.industry_prosperity, f"行业景气分 {components.industry_prosperity:.0f}，主题与正向验证仍在累积。"),
            ("龙头位置", components.leader_position, f"龙头位置分 {components.leader_position:.0f}，当前市值约 {_fmt_billions(market_cap, currency='¥')}。"),
            ("财务加速", components.financial_acceleration, f"财务加速分 {components.financial_acceleration:.0f}，收入与利润仍在兑现。"),
            ("现金流质量", components.cashflow_quality, f"现金流质量分 {components.cashflow_quality:.0f}，经营现金流与利润匹配度可用。"),
            ("研发护城河", components.moat, f"研发护城河分 {components.moat:.0f}，研发投入仍在支撑下一轮增长。"),
            ("估值筹码", components.valuation_chip, f"估值筹码分 {components.valuation_chip:.0f}，PE {pe_text} / PB {pb_text}。"
             if pe_ttm is not None or pb is not None
             else f"估值筹码分 {components.valuation_chip:.0f}，估值口径暂不完整。"),
        ]
        return [note for _label, _score, note in sorted(drivers, key=lambda item: item[1], reverse=True)[:3]]

    drivers = [
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
    market: TenxMarket = "US",
    ps_ttm: float | None = None,
    pe_ttm: float | None = None,
    pb: float | None = None,
    market_cap: float | None = None,
    return_5d: float | None = None,
    distance_from_high: float | None = None,
) -> CandidateExplanation:
    driver_notes = build_score_driver_notes(
        components,
        market=market,
        ps_ttm=ps_ttm,
        pe_ttm=pe_ttm,
        pb=pb,
        market_cap=market_cap,
        return_5d=return_5d,
        distance_from_high=distance_from_high,
    )
    if market == "CN":
        stage_reason_map = {
            "discovery": "处于 discovery 阶段：赛道和主题成立，但需要更多财务与事件验证。",
            "validation": "处于 validation 阶段：产业逻辑开始兑现，关键指标进入可验证区间。",
            "acceleration": "处于 acceleration 阶段：财务与景气共振，最接近主升浪前的研究窗口。",
            "crowded": "处于 crowded 阶段：逻辑已被充分认知，赔率开始被估值与筹码压缩。",
            "falsified": "处于 falsified 阶段：核心假设受损，应该优先复核而不是加仓研究。",
        }
        crowding_note = (
            "当前更需要关注估值与筹码是否已经透支后续兑现。"
            if stage == "crowded"
            else "目前尚未出现明显的赔率拥挤信号。"
        )
        return CandidateExplanation(
            selection_reason=f"该标的进入主候选池，核心由 {explain_components(components, market='CN')} 驱动。",
            stage_reason=stage_reason_map[stage],
            crowding_note=crowding_note,
            score_drivers=driver_notes,
        )

    stage_reason_map = {
        "discovery": "处于 discovery 阶段：主线成立，但还需要更多基本面验证。",
        "validation": "处于 validation 阶段：增长与证据开始匹配，已进入重点跟踪区。",
        "acceleration": "处于 acceleration 阶段：收入、利润和验证信号开始同步强化。",
        "crowded": "处于 crowded 阶段：市场已广泛认知这条逻辑，赔率正在下降。",
        "falsified": "处于 falsified 阶段：近期负面信号已足以破坏原始假设。",
    }
    crowding_note = (
        "当前最需要警惕的是，大票拥挤与短期过热可能让赔率下降快于基本面兑现。"
        if stage == "crowded"
        else "目前尚未出现更明确的拥挤迹象，可以继续把重心放在证据累积与财务验证。"
    )
    return CandidateExplanation(
        selection_reason=f"该标的进入主候选池，主要由 {explain_components(components)} 驱动。",
        stage_reason=stage_reason_map[stage],
        crowding_note=crowding_note,
        score_drivers=driver_notes,
    )
