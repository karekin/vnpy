from __future__ import annotations

from enum import Enum, IntEnum


class FactorCategory(str, Enum):
    BASE = "base"
    HISTORY = "history"
    STOCK = "stk"


class FunctionCategory(str, Enum):
    CROSS_SECTION = "cross_section"
    TIME_SERIES = "time_series"
    MATH = "math"
    OTHER = "other"
    TECHNICAL = "technical"
    LOGIC = "logic"
    CALENDAR = "calendar"


class FactorType(IntEnum):
    DEFAULT = 0
    DERIVED = 2
    ADVANCED = 3


class ExpressionType(IntEnum):
    NUMERIC = 1
    TEXT = 2
