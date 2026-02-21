import ctypes
import platform
import sys
import traceback
import webbrowser
import types
import threading

import qdarkstyle  # type: ignore
from PySide6 import QtGui, QtWidgets, QtCore
from loguru import logger

from ..setting import SETTINGS
from ..utility import get_icon_path
from ..locale import _


Qt = QtCore.Qt


def create_qapp(app_name: str = "VeighNa Trader") -> QtWidgets.QApplication:
    """
    Create Qt Application.
    """
    # Set up dark stylesheet
    qapp: QtWidgets.QApplication = QtWidgets.QApplication(sys.argv)
    qapp.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyside6"))

    # Set up font
    font: QtGui.QFont = QtGui.QFont(SETTINGS["font.family"], SETTINGS["font.size"])
    qapp.setFont(font)

    # Set up icon
    icon: QtGui.QIcon = QtGui.QIcon(get_icon_path(__file__, "vnpy.ico"))
    qapp.setWindowIcon(icon)

    # Set up windows process ID
    if "Windows" in platform.uname():
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            app_name
        )

    # Exception Handling
    exception_widget: ExceptionWidget = ExceptionWidget()

    def excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_traceback: types.TracebackType | None
    ) -> None:
        """Show exception detail with QMessageBox."""
        logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("Main thread exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

        msg: str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        exception_widget.signal.emit(msg)

    sys.excepthook = excepthook

    def threading_excepthook(args: threading.ExceptHookArgs) -> None:
        """Show exception detail from background threads with QMessageBox."""
        if args.exc_value and args.exc_traceback:
            logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).critical("Background thread exception")
            sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)

        msg: str = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        exception_widget.signal.emit(msg)

    threading.excepthook = threading_excepthook

    return qapp


class ExceptionWidget(QtWidgets.QWidget):
    """
    `ExceptionWidget` 是异常弹窗组件，用于在 GUI 中展示未捕获异常堆栈。
    
    职责：
    1. 将异常信息格式化为可阅读文本。
    2. 在界面层提供错误反馈，避免异常静默。
    3. 辅助用户快速定位运行问题。
    
    协作：
    1. 通常由全局异常钩子触发。
    2. 与日志系统配合形成“弹窗 + 持久日志”双通道告警。
    """
    signal: QtCore.Signal = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `parent` (`QtWidgets.QWidget | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(parent)

        self.init_ui()
        self.signal.connect(self.show_exception)

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
        self.setWindowTitle(_("触发异常"))
        self.setFixedSize(600, 600)

        self.msg_edit: QtWidgets.QTextEdit = QtWidgets.QTextEdit()
        self.msg_edit.setReadOnly(True)

        copy_button: QtWidgets.QPushButton = QtWidgets.QPushButton(_("复制"))
        copy_button.clicked.connect(self._copy_text)

        community_button: QtWidgets.QPushButton = QtWidgets.QPushButton(_("求助"))
        community_button.clicked.connect(self._open_community)

        close_button: QtWidgets.QPushButton = QtWidgets.QPushButton(_("关闭"))
        close_button.clicked.connect(self.close)

        hbox: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        hbox.addWidget(copy_button)
        hbox.addWidget(community_button)
        hbox.addWidget(close_button)

        vbox: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.msg_edit)
        vbox.addLayout(hbox)

        self.setLayout(vbox)

    def show_exception(self, msg: str) -> None:
        """
        执行 `show_exception` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `msg` (`str`)：日志或提示消息文本。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.msg_edit.setText(msg)
        self.show()

    def _copy_text(self) -> None:
        """
        执行 `_copy_text` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.msg_edit.selectAll()
        self.msg_edit.copy()

    def _open_community(self) -> None:
        """
        执行 `_open_community` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        webbrowser.open("https://www.vnpy.com/forum/forum/2-ti-wen-qiu-zhu")
