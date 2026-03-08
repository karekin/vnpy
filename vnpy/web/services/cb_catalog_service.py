"""CB Quant 因子/函数目录服务。

这个模块不做任何回测或行情计算，只负责把注册表里的元数据整理成
前端可直接消费的 catalog 响应，方便页面做：

1. 因子选择器
2. 表达式编辑器提示
3. 函数说明面板
"""

from __future__ import annotations

from vnpy.web.domain.cb_quant.enums import FactorCategory, FunctionCategory
from vnpy.web.domain.cb_quant.factor_support import factor_support_level, is_template_selectable_factor
from vnpy.web.domain.cb_quant.registry import FACTOR_REGISTRY, FUNCTION_REGISTRY
from vnpy.web.domain.cb_quant.strategy_factor_registry import (
    build_strategy_factor_usage_hint,
    get_strategy_factor_definition,
)
from vnpy.web.contracts.cb_quant import (
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
    """CB Quant 目录查询服务。

    设计目标很简单：把 domain 层定义好的静态注册表转换成 API schema。
    这里不依赖数据库，也不做缓存状态管理，因此适合作为“纯只读”服务。
    """

    def list_factors(
        self,
        *,
        category: str = "all",
        keyword: str = "",
        enabled_only: bool = False,
        template_only: bool = False,
    ) -> FactorCatalogResponse:
        """按分类和关键字返回因子目录。

        - `category="all"` 时遍历全部因子分类
        - `enabled_only=True` 时只返回前端允许启用的因子
        - `keyword` 同时匹配名称、key、表达式文本
        """
        needle = keyword.strip().lower()
        category_enum = self._parse_factor_category(category)
        categories = [category_enum] if category_enum else list(FactorCategory)

        blocks: list[FactorCatalogCategory] = []
        total_factors = 0

        for factor_category in categories:
            rows: list[FactorCatalogRow] = []
            for factor in FACTOR_REGISTRY.get(factor_category, ()):
                strategy_definition = get_strategy_factor_definition(factor.factor_key)
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
                        support_level=factor_support_level(factor.factor_key).value,
                        template_selectable=is_template_selectable_factor(factor.factor_key),
                        strategy_kind=strategy_definition.kind.value if strategy_definition else "plain",
                        setting_key=strategy_definition.setting_key if strategy_definition else None,
                        usage_hint=build_strategy_factor_usage_hint(strategy_definition) if strategy_definition else "",
                        param_value_type=strategy_definition.value_type if strategy_definition else None,
                        param_min_value=strategy_definition.min_value if strategy_definition else None,
                        param_max_value=strategy_definition.max_value if strategy_definition else None,
                        param_step=strategy_definition.step if strategy_definition else None,
                        param_enum_values=list(strategy_definition.enum_values) if strategy_definition else [],
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
        """按分类和关键字返回函数目录。"""
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
        """把 URL 查询参数解析成枚举；非法值按 all 处理。"""
        if category == "all":
            return None
        try:
            return FactorCategory(category)
        except ValueError:
            return None

    @staticmethod
    def _parse_function_category(category: str) -> FunctionCategory | None:
        """把函数分类字符串解析成枚举；非法值按 all 处理。"""
        if category == "all":
            return None
        try:
            return FunctionCategory(category)
        except ValueError:
            return None
