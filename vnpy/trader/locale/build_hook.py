from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po


class LocaleBuildHook(BuildHookInterface):
    """
    `LocaleBuildHook` 是打包构建阶段的本地化处理钩子。
    
    职责：
    1. 在构建流程中处理翻译资源或语言包相关任务。
    2. 确保发行包包含可用的本地化文件。
    3. 把多语言处理接入统一构建生命周期。
    
    协作：
    1. 由打包工具通过 Hook 接口调用。
    2. 与 `vnpy/trader/locale` 目录资源协同。
    """

    def initialize(self, version: str, build_data: dict) -> None:
        """
        执行 `initialize` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `version` (`str`)：输入参数，用于控制该方法的处理行为。
        2. `build_data` (`dict`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        # Only generate mo file when building wheel
        if "pure_python" not in build_data:
            return

        self.locale_path: Path = Path(self.root).joinpath("vnpy", "trader", "locale")
        self.mo_path: Path = self.locale_path.joinpath("en", "LC_MESSAGES", "vnpy.mo")
        self.po_path: Path = self.locale_path.joinpath("en", "LC_MESSAGES", "vnpy.po")

        with open(self.mo_path, "wb") as mo_f:
            with open(self.po_path, encoding="utf-8") as po_f:
                write_mo(mo_f, read_po(po_f))
