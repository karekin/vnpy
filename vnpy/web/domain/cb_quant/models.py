from __future__ import annotations

from dataclasses import dataclass, field

from vnpy.web.domain.cb_quant.enums import ExpressionType, FactorCategory, FactorType, FunctionCategory


@dataclass(frozen=True)
class FactorMeta:
    id: str
    factor_name: str
    factor_key: str
    category: FactorCategory
    factor_type: FactorType
    expression: str
    expression_type: ExpressionType
    enabled: bool
    remark: str = ""
    view_style: int = 0
    view_precision: int = 2
    view_color: bool = False
    view_ratio: float = 1
    view_unit: str = ""


@dataclass(frozen=True)
class FunctionParameterMeta:
    name: str
    description: str
    type_name: str
    type: str


@dataclass(frozen=True)
class FunctionMeta:
    category: FunctionCategory
    name: str
    formular: str
    description: str
    parameters: list[FunctionParameterMeta] = field(default_factory=list)

    @property
    def parameter_size(self) -> int:
        return len(self.parameters)
