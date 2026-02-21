"""
Implements main window of the trading platform.
"""

from types import ModuleType
import webbrowser
from functools import partial
from importlib import import_module
from typing import TypeVar
from collections.abc import Callable

import vnpy
from vnpy.event import EventEngine

from .qt import QtCore, QtGui, QtWidgets
from .widget import (
    BaseMonitor,
    TickMonitor,
    OrderMonitor,
    TradeMonitor,
    PositionMonitor,
    AccountMonitor,
    LogMonitor,
    ActiveOrderMonitor,
    ConnectDialog,
    ContractManager,
    TradingWidget,
    AboutDialog,
    GlobalDialog
)
from ..engine import MainEngine, BaseApp
from ..utility import get_icon_path, TRADER_DIR
from ..locale import _


WidgetType = TypeVar("WidgetType", bound="QtWidgets.QWidget")


class MainWindow(QtWidgets.QMainWindow):
    """
    `MainWindow` 是 vn.py 桌面终端主窗口，负责菜单、停靠面板与应用入口整合。
    
    职责：
    1. 加载并管理各监控面板与交易面板。
    2. 承载网关连接、日志查看、合约查询等主流程入口。
    3. 统一管理应用插件 UI 的挂载与布局恢复。
    
    协作：
    1. 与 `MainEngine` 协作执行交易命令。
    2. 与 `BaseApp` 提供的 widget 信息联动动态加载界面。
    """

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `main_engine` (`MainEngine`)：输入参数，用于控制该方法的处理行为。
        2. `event_engine` (`EventEngine`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine

        self.window_title: str = _("VeighNa Trader 社区版 - {}   [{}]").format(vnpy.__version__, TRADER_DIR)

        self.widgets: dict[str, QtWidgets.QWidget] = {}
        self.monitors: dict[str, BaseMonitor] = {}

        self.init_ui()

    def init_ui(self) -> None:
        """
        执行 `init_ui` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.setWindowTitle(self.window_title)
        self.init_dock()
        self.init_toolbar()
        self.init_menu()
        self.load_window_setting("custom")

    def init_dock(self) -> None:
        """
        执行 `init_dock` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.trading_widget, trading_dock = self.create_dock(
            TradingWidget, _("交易"), QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
        )
        tick_widget, tick_dock = self.create_dock(
            TickMonitor, _("行情"), QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        )
        order_widget, order_dock = self.create_dock(
            OrderMonitor, _("委托"), QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        )
        active_widget, active_dock = self.create_dock(
            ActiveOrderMonitor, _("活动"), QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        )
        trade_widget, trade_dock = self.create_dock(
            TradeMonitor, _("成交"), QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        )
        log_widget, log_dock = self.create_dock(
            LogMonitor, _("日志"), QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
        )
        account_widget, account_dock = self.create_dock(
            AccountMonitor, _("资金"), QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
        )
        position_widget, position_dock = self.create_dock(
            PositionMonitor, _("持仓"), QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
        )

        self.tabifyDockWidget(active_dock, order_dock)

        self.save_window_setting("default")

        tick_widget.itemDoubleClicked.connect(self.trading_widget.update_with_cell)
        position_widget.itemDoubleClicked.connect(self.trading_widget.update_with_cell)

    def init_menu(self) -> None:
        """
        执行 `init_menu` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        bar: QtWidgets.QMenuBar = self.menuBar()
        bar.setNativeMenuBar(False)     # for mac and linux

        # System menu
        sys_menu: QtWidgets.QMenu = bar.addMenu(_("系统"))

        gateway_names: list = self.main_engine.get_all_gateway_names()
        for name in gateway_names:
            func: Callable = partial(self.connect_gateway, name)
            self.add_action(
                sys_menu,
                _("连接{}").format(name),
                get_icon_path(__file__, "connect.ico"),
                func
            )

        sys_menu.addSeparator()

        self.add_action(
            sys_menu,
            _("退出"),
            get_icon_path(__file__, "exit.ico"),
            self.close
        )

        # App menu
        app_menu: QtWidgets.QMenu = bar.addMenu(_("功能"))

        all_apps: list[BaseApp] = self.main_engine.get_all_apps()
        for app in all_apps:
            ui_module: ModuleType = import_module(app.app_module + ".ui")
            widget_class: type[QtWidgets.QWidget] = getattr(ui_module, app.widget_name)

            func = partial(self.open_widget, widget_class, app.app_name)

            self.add_action(app_menu, app.display_name, app.icon_name, func, True)

        # Global setting editor
        action: QtGui.QAction = QtGui.QAction(_("配置"), self)
        action.triggered.connect(self.edit_global_setting)
        bar.addAction(action)

        # Help menu
        help_menu: QtWidgets.QMenu = bar.addMenu(_("帮助"))

        self.add_action(
            help_menu,
            _("查询合约"),
            get_icon_path(__file__, "contract.ico"),
            partial(self.open_widget, ContractManager, "contract"),
            True
        )

        self.add_action(
            help_menu,
            _("还原窗口"),
            get_icon_path(__file__, "restore.ico"),
            self.restore_window_setting
        )

        self.add_action(
            help_menu,
            _("测试邮件"),
            get_icon_path(__file__, "email.ico"),
            self.send_test_email
        )

        self.add_action(
            help_menu,
            _("社区论坛"),
            get_icon_path(__file__, "forum.ico"),
            self.open_forum,
            True
        )

        self.add_action(
            help_menu,
            _("关于"),
            get_icon_path(__file__, "about.ico"),
            partial(self.open_widget, AboutDialog, "about"),
        )

    def init_toolbar(self) -> None:
        """
        执行 `init_toolbar` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.toolbar: QtWidgets.QToolBar = QtWidgets.QToolBar(self)
        self.toolbar.setObjectName(_("工具栏"))
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)

        # Set button size
        w: int = 40
        size = QtCore.QSize(w, w)
        self.toolbar.setIconSize(size)

        # Set button spacing
        layout: QtWidgets.QLayout | None = self.toolbar.layout()
        if layout:
            layout.setSpacing(10)

        self.addToolBar(QtCore.Qt.ToolBarArea.LeftToolBarArea, self.toolbar)

    def add_action(
        self,
        menu: QtWidgets.QMenu,
        action_name: str,
        icon_name: str,
        func: Callable,
        toolbar: bool = False
    ) -> None:
        """
        新增 `action` 相关对象或配置项。
        
        用途说明：
        1. 对内部状态进行更新，并维护相关数据一致性。
        2. 如涉及联动依赖，应在本方法内完成必要同步。
        
        参数：
        1. `menu` (`QtWidgets.QMenu`)：输入参数，用于控制该方法的处理行为。
        2. `action_name` (`str`)：输入参数，用于控制该方法的处理行为。
        3. `icon_name` (`str`)：输入参数，用于控制该方法的处理行为。
        4. `func` (`Callable`)：输入参数，用于控制该方法的处理行为。
        5. `toolbar` (`bool`)，默认值 `False`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        icon: QtGui.QIcon = QtGui.QIcon(icon_name)

        action: QtGui.QAction = QtGui.QAction(action_name, self)
        action.triggered.connect(func)
        action.setIcon(icon)

        menu.addAction(action)

        if toolbar:
            self.toolbar.addAction(action)

    def create_dock(
        self,
        widget_class: type[WidgetType],
        name: str,
        area: QtCore.Qt.DockWidgetArea
    ) -> tuple[WidgetType, QtWidgets.QDockWidget]:
        """
        执行 `create_dock` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `widget_class` (`type[WidgetType]`)：输入参数，用于控制该方法的处理行为。
        2. `name` (`str`)：输入参数，用于控制该方法的处理行为。
        3. `area` (`QtCore.Qt.DockWidgetArea`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `tuple[WidgetType, QtWidgets.QDockWidget]`：返回多个值组成的结果元组。
        """
        widget: WidgetType = widget_class(self.main_engine, self.event_engine)      # type: ignore
        if isinstance(widget, BaseMonitor):
            self.monitors[name] = widget

        dock: QtWidgets.QDockWidget = QtWidgets.QDockWidget(name)
        dock.setWidget(widget)
        dock.setObjectName(name)
        dock.setFeatures(dock.DockWidgetFeature.DockWidgetFloatable | dock.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(area, dock)
        return widget, dock

    def connect_gateway(self, gateway_name: str) -> None:
        """
        执行 `connect_gateway` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `gateway_name` (`str`)：网关名称，用于定位目标网关实例。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        dialog: ConnectDialog = ConnectDialog(self.main_engine, gateway_name)
        dialog.exec()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        执行 `closeEvent` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `event` (`QtGui.QCloseEvent`)：事件对象，通常通过 `event.data` 携带业务数据。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        reply = QtWidgets.QMessageBox.question(
            self,
            _("退出"),
            _("确认退出？"),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            for widget in self.widgets.values():
                widget.close()

            for monitor in self.monitors.values():
                monitor.save_setting()

            self.save_window_setting("custom")

            self.main_engine.close()

            event.accept()
        else:
            event.ignore()

    def open_widget(self, widget_class: type[QtWidgets.QWidget], name: str) -> None:
        """
        执行 `open_widget` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `widget_class` (`type[QtWidgets.QWidget]`)：输入参数，用于控制该方法的处理行为。
        2. `name` (`str`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        widget: QtWidgets.QWidget | None = self.widgets.get(name, None)
        if not widget:
            widget = widget_class(self.main_engine, self.event_engine)      # type: ignore
            self.widgets[name] = widget

        if isinstance(widget, QtWidgets.QDialog):
            widget.exec()
        else:
            widget.show()

    def save_window_setting(self, name: str) -> None:
        """
        保存 `window_setting` 相关内容。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `name` (`str`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        settings: QtCore.QSettings = QtCore.QSettings(self.window_title, name)
        settings.setValue("state", self.saveState())
        settings.setValue("geometry", self.saveGeometry())

    def load_window_setting(self, name: str) -> None:
        """
        加载 `window_setting` 相关资源。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `name` (`str`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        settings: QtCore.QSettings = QtCore.QSettings(self.window_title, name)
        state = settings.value("state")
        geometry = settings.value("geometry")

        if isinstance(state, QtCore.QByteArray):
            self.restoreState(state)
            self.restoreGeometry(geometry)

    def restore_window_setting(self) -> None:
        """
        执行 `restore_window_setting` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.load_window_setting("default")
        self.showMaximized()

    def send_test_email(self) -> None:
        """
        发送 `test_email` 请求并处理返回结果。
        
        用途说明：
        1. 与外部系统或底层组件交互，完成动作请求。
        2. 处理成功与异常分支，确保状态可追踪。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.main_engine.send_email("VeighNa Trader", "testing", None)

    def open_forum(self) -> None:
        """
        执行 `open_forum` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        webbrowser.open("https://www.vnpy.com/forum/")

    def edit_global_setting(self) -> None:
        """
        执行 `edit_global_setting` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        dialog: GlobalDialog = GlobalDialog()
        dialog.exec()
