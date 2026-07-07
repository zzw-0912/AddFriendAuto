"""
输入控制器管理器

统一管理所有输入引擎实例，键盘和鼠标独立选择。
输入方式由全局控制，节点不感知输入方式。
"""
import threading
from typing import Dict, Optional, Any

from .base_input import BaseInputController, BaseKeyboardController, BaseMouseController, InputLevel


class InputControllerManager:
    """输入控制器管理器（单例）

    核心职责：
    1. 管理所有引擎实例（单例池）
    2. 键盘和鼠标独立选择引擎
    3. 引擎可用性检测
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._keyboard_engines: Dict[str, BaseKeyboardController] = {}
        self._mouse_engines: Dict[str, BaseMouseController] = {}
        self._keyboard_method: str = self._load_keyboard_method()
        self._mouse_method: str = self._load_mouse_method()

    def _load_keyboard_method(self) -> str:
        """从 SettingsManager 加载键盘输入方式"""
        try:
            from config.settings_manager import SettingsManager
            return SettingsManager.get_instance().get("input.keyboard_method", "pyautogui")
        except Exception:
            return "pyautogui"

    def _load_mouse_method(self) -> str:
        """从 SettingsManager 加载鼠标输入方式"""
        try:
            from config.settings_manager import SettingsManager
            return SettingsManager.get_instance().get("input.mouse_method", "pyautogui")
        except Exception:
            return "pyautogui"

    def get_keyboard_method(self) -> str:
        return self._keyboard_method

    def get_mouse_method(self) -> str:
        return self._mouse_method

    def set_keyboard_method(self, method: str) -> None:
        self._keyboard_method = method
        try:
            from config.settings_manager import SettingsManager
            SettingsManager.get_instance().set("input.keyboard_method", method)
        except Exception:
            pass

    def set_mouse_method(self, method: str) -> None:
        self._mouse_method = method
        try:
            from config.settings_manager import SettingsManager
            SettingsManager.get_instance().set("input.mouse_method", method)
        except Exception:
            pass

    def get_keyboard_engine(self, **kwargs) -> Optional[BaseKeyboardController]:
        """获取键盘引擎"""
        method = self._keyboard_method

        if method == "bg":
            return self._create_bg_engine(**kwargs)

        if method not in self._keyboard_engines:
            engine = self._create_engine(method)
            if engine is None:
                return None
            self._keyboard_engines[method] = engine

        return self._keyboard_engines.get(method)

    def get_mouse_engine(self, **kwargs) -> Optional[BaseMouseController]:
        """获取鼠标引擎"""
        method = self._mouse_method

        if method == "bg":
            return self._create_bg_engine(**kwargs)

        if method not in self._mouse_engines:
            engine = self._create_engine(method)
            if engine is None:
                return None
            self._mouse_engines[method] = engine

        return self._mouse_engines.get(method)

    def get_engine(self, **kwargs) -> Optional[BaseInputController]:
        """兼容方法：返回键盘引擎"""
        return self.get_keyboard_engine(**kwargs)

    def _create_engine(self, method: str) -> Optional[BaseInputController]:
        """创建指定方法的引擎实例"""
        if method == "pyautogui":
            from .input_controller_factory import PyAutoGUIInput
            return PyAutoGUIInput()
        elif method == "dd":
            return self._create_dd_engine()
        elif method == "ib":
            return self._create_ib_engine()
        return None

    def _create_dd_engine(self) -> Optional[BaseInputController]:
        try:
            from .input_controller_factory import _get_dd_input, DDInputWrapper
            dd_instance = _get_dd_input()
            if dd_instance and dd_instance.is_available:
                return DDInputWrapper(dd_instance)
        except Exception:
            pass
        return None

    def _create_ib_engine(self) -> Optional[BaseInputController]:
        try:
            from .ib_input import IbInputSimulatorInput
            if IbInputSimulatorInput.is_driver_available():
                engine = IbInputSimulatorInput()
                if engine.is_available:
                    return engine
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def _create_bg_engine(self, **kwargs) -> Optional[BaseInputController]:
        hwnd = kwargs.get("hwnd", 0)
        if not hwnd:
            return None
        try:
            from .bg_input import BackgroundInputController
            engine = BackgroundInputController(hwnd=hwnd)
            if engine.is_available:
                return engine
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def get_available_methods(self) -> Dict[str, Dict[str, Any]]:
        """获取所有可用输入方式"""
        methods = {}

        methods["pyautogui"] = {
            "name": "PyAutoGUI",
            "level": InputLevel.APPLICATION,
            "available": True,
            "requires_admin": False,
        }

        try:
            from .dd_input import DDVirtualInput
            dd_available = DDVirtualInput.is_driver_available()
        except Exception:
            dd_available = False
        methods["dd"] = {
            "name": "DD虚拟键盘",
            "level": InputLevel.DRIVER,
            "available": dd_available,
            "requires_admin": True,
        }

        try:
            from .ib_input import IbInputSimulatorInput, detect_ib_driver_status
            ib_available = IbInputSimulatorInput.is_driver_available()
            ib_driver_status = detect_ib_driver_status()
        except ImportError:
            ib_available = False
            ib_driver_status = {}
        except Exception:
            ib_available = False
            ib_driver_status = {}
        methods["ib"] = {
            "name": "IbInputSimulator",
            "level": InputLevel.DRIVER,
            "available": ib_available,
            "requires_admin": True,
            "driver_status": ib_driver_status,
        }

        methods["bg"] = {
            "name": "后台消息",
            "level": InputLevel.BACKGROUND,
            "available": True,
            "requires_admin": False,
        }

        return methods

    def cleanup(self) -> None:
        """清理所有引擎实例"""
        seen = set()
        for engines in [self._keyboard_engines, self._mouse_engines]:
            for method, engine in engines.items():
                if id(engine) not in seen:
                    seen.add(id(engine))
                    try:
                        if hasattr(engine, 'cleanup'):
                            engine.cleanup()
                    except Exception:
                        pass
        self._keyboard_engines.clear()
        self._mouse_engines.clear()

    @classmethod
    def reset_instance(cls):
        if cls._instance is not None:
            cls._instance.cleanup()
        cls._instance = None
