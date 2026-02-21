from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .engine import BaseEngine


class BaseApp(ABC):
    """
    `BaseApp` 是 vn.py 应用插件的元信息声明类，用来描述一个 App 如何被主引擎发现、加载和展示。
    
    职责：
    1. 声明应用标识（`app_name`、`display_name`）和模块归属（`app_module`、`app_path`）。
    2. 指定应用对应的功能引擎类 `engine_class`，供 `MainEngine.add_app()` 动态实例化。
    3. 声明可选界面入口（`widget_name`、`icon_name`），供主窗口挂载菜单与图标。
    
    协作：
    1. 由 `MainEngine` 读取该类字段并完成应用注册。
    2. 与具体 AppEngine、UI Widget 配套组成完整功能模块。
    """

    app_name: str                       # Unique name used for creating engine and widget
    app_module: str                     # App module string used in import_module
    app_path: Path                      # Absolute path of app folder
    display_name: str                   # Name for display on the menu.
    engine_class: type["BaseEngine"]    # App engine class
    widget_name: str                    # Class name of app widget
    icon_name: str                      # Icon file name of app widget
