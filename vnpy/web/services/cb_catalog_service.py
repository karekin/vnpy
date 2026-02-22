from __future__ import annotations

from vnpy.web.domain.cb_quant.enums import FactorCategory, FunctionCategory
from vnpy.web.domain.cb_quant.registry import FACTOR_REGISTRY, FUNCTION_REGISTRY
from vnpy.web.schemas import (
    FactorCatalogCategory,
    FactorCatalogResponse,
    FactorCatalogRow,
    FunctionCatalogCategory,
    FunctionCatalogResponse,
    FunctionCatalogRow,
    FunctionParameterCatalogRow,
)


FACTOR_CATEGORY_LABELS: dict[FactorCategory, str] = {
    FactorCategory.BASE: "基础因子",
    FactorCategory.HISTORY: "历史类因子",
    FactorCategory.STOCK: "正股相关因子",
}

FUNCTION_CATEGORY_LABELS: dict[FunctionCategory, str] = {
    FunctionCategory.CROSS_SECTION: "截面函数",
    FunctionCategory.TIME_SERIES: "时序函数",
    FunctionCategory.MATH: "数学函数",
    FunctionCategory.OTHER: "其他函数",
    FunctionCategory.TECHNICAL: "技术指标",
    FunctionCategory.LOGIC: "逻辑函数",
    FunctionCategory.CALENDAR: "日历函数",
}


class CbCatalogService:
    """CB Quant factor/function catalog service."""

    def list_factors(
        self,
        *,
        category: str = "all",
        keyword: str = "",
        enabled_only: bool = False,
    ) -> FactorCatalogResponse:
        needle = keyword.strip().lower()
        category_enum = self._parse_factor_category(category)
        categories = [category_enum] if category_enum else list(FactorCategory)

        blocks: list[FactorCatalogCategory] = []
        total_factors = 0

        for factor_category in categories:
            rows: list[FactorCatalogRow] = []
            for factor in FACTOR_REGISTRY.get(factor_category, ()):
                if enabled_only and not factor.enabled:
                    continue
                if needle:
                    raw = f"{factor.factor_name}|{factor.factor_key}|{factor.expression}".lower()
                    if needle not in raw:
                        continue
                rows.append(
                    FactorCatalogRow(
                        id=factor.id,
                        factor_name=factor.factor_name,
                        factor_key=factor.factor_key,
                        factor_type=int(factor.factor_type),
                        expression=factor.expression,
                        expression_type=int(factor.expression_type),
                        enabled=factor.enabled,
                        remark=factor.remark,
                        view_style=factor.view_style,
                        view_precision=factor.view_precision,
                        view_color=factor.view_color,
                        view_ratio=factor.view_ratio,
                        view_unit=factor.view_unit,
                    )
                )

            if rows:
                total_factors += len(rows)
                blocks.append(
                    FactorCatalogCategory(
                        category_name=FACTOR_CATEGORY_LABELS[factor_category],
                        category_key=factor_category.value,
                        factors=rows,
                    )
                )

        return FactorCatalogResponse(
            items=blocks,
            total_categories=len(blocks),
            total_factors=total_factors,
        )

    def list_functions(
        self,
        *,
        category: str = "all",
        keyword: str = "",
    ) -> FunctionCatalogResponse:
        needle = keyword.strip().lower()
        category_enum = self._parse_function_category(category)
        categories = [category_enum] if category_enum else list(FunctionCategory)

        blocks: list[FunctionCatalogCategory] = []
        total_functions = 0

        for function_category in categories:
            rows: list[FunctionCatalogRow] = []
            for function_meta in FUNCTION_REGISTRY.get(function_category, ()):
                if needle:
                    raw = f"{function_meta.name}|{function_meta.formular}|{function_meta.description}".lower()
                    if needle not in raw:
                        continue
                rows.append(
                    FunctionCatalogRow(
                        name=function_meta.name,
                        formular=function_meta.formular,
                        description=function_meta.description,
                        parameter_size=function_meta.parameter_size,
                        parameters=[
                            FunctionParameterCatalogRow(
                                name=parameter.name,
                                description=parameter.description,
                                type_name=parameter.type_name,
                                type=parameter.type,
                            )
                            for parameter in function_meta.parameters
                        ],
                    )
                )

            if rows:
                total_functions += len(rows)
                blocks.append(
                    FunctionCatalogCategory(
                        category_name=FUNCTION_CATEGORY_LABELS[function_category],
                        category_key=function_category.value,
                        functions=rows,
                    )
                )

        return FunctionCatalogResponse(
            items=blocks,
            total_categories=len(blocks),
            total_functions=total_functions,
        )

    @staticmethod
    def _parse_factor_category(category: str) -> FactorCategory | None:
        if category == "all":
            return None
        try:
            return FactorCategory(category)
        except ValueError:
            return None

    @staticmethod
    def _parse_function_category(category: str) -> FunctionCategory | None:
        if category == "all":
            return None
        try:
            return FunctionCategory(category)
        except ValueError:
            return None
