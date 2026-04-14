from __future__ import annotations

from dataclasses import dataclass
import html
import re
from typing import Iterable


POSITIVE_KEYWORDS = {
    "beat",
    "acceleration",
    "strong",
    "record",
    "expanded",
    "upside",
    "win",
    "demand",
    "partnership",
    "launch",
}
NEGATIVE_KEYWORDS = {
    "delay",
    "slowdown",
    "miss",
    "pressure",
    "breach",
    "risk",
    "lawsuit",
    "regulation",
    "outage",
    "downgrade",
}
RISK_KEYWORDS = {
    "execution": {"delay", "slowdown", "miss"},
    "security": {"breach", "outage"},
    "regulation": {"regulation", "lawsuit"},
    "competitive": {"pressure", "downgrade"},
}
THEME_KEYWORDS = {
    "ai_infra": {"ai", "gpu", "inference", "training", "accelerator", "data center", "compute"},
    "cloud": {"cloud", "data platform", "consumption", "warehouse", "lakehouse"},
    "cybersecurity": {"security", "endpoint", "identity", "threat", "breach"},
    "semis": {"semiconductor", "chip", "wafer", "hbm", "cpu", "gpu"},
}


@dataclass(frozen=True)
class Signal:
    summary: str
    sentiment: str
    risk_tags: list[str]
    theme_tags: list[str]
    importance: int
    positive_hits: int
    negative_hits: int


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(text: str) -> str:
    without_tags = _HTML_TAG_RE.sub(" ", text)
    unescaped = html.unescape(without_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


def _contains_keyword(text: str, keyword: str) -> bool:
    if " " in keyword:
        return keyword in text
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _count_hits(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for keyword in keywords if _contains_keyword(text, keyword))


def extract_signal(text: str) -> Signal:
    cleaned = _clean_text(text)
    focus_text = cleaned[:8000]
    lowered = focus_text.lower()
    positive_hits = _count_hits(lowered, POSITIVE_KEYWORDS)
    negative_hits = _count_hits(lowered, NEGATIVE_KEYWORDS)

    theme_tags = [theme for theme, keywords in THEME_KEYWORDS.items() if any(word in lowered for word in keywords)]
    risk_tags = [risk for risk, keywords in RISK_KEYWORDS.items() if any(word in lowered for word in keywords)]

    if positive_hits > negative_hits:
        sentiment = "positive"
    elif negative_hits > positive_hits:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    parts = [part.strip() for part in _SENTENCE_SPLIT.split(cleaned) if part.strip()]
    summary = parts[0] if parts else cleaned
    summary = summary[:220]

    importance = max(1, min(5, 1 + len(theme_tags) + max(positive_hits, negative_hits)))

    return Signal(
        summary=summary,
        sentiment=sentiment,
        risk_tags=sorted(set(risk_tags)),
        theme_tags=sorted(set(theme_tags)),
        importance=importance,
        positive_hits=positive_hits,
        negative_hits=negative_hits,
    )
