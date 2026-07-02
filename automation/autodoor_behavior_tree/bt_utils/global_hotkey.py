import threading
import time
import logging
from typing import Callable, Dict, Optional
from pynput import keyboard
from .key_name_resolver import resolve_key_name


logger = logging.getLogger(__name__)


class GlobalHotkeyManager:
    """全局热键管理器
    
    使用 pynput 库实现全局热键监听，支持在窗口失去焦点时也能响应快捷键。
    添加了优化来减少被 pyautogui 模拟按键干扰的可能性。
    """
    
    _instance: Optional["GlobalHotkeyManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._listener: Optional[keyboard.Listener] = None
        self._hotkeys: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._running = False
        self._last_trigger_time: Dict[str, float] = {}
        self._debounce_interval = 0.1
        self._pressed_modifiers: set = set()  # 当前按下的修饰键
    
    @classmethod
    def get_instance(cls) -> "GlobalHotkeyManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        if cls._instance is not None:
            cls._instance.stop()
            cls._instance = None
    
    def start(self):
        """启动全局热键监听"""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
                suppress=False
            )
            self._listener.start()
    
    def stop(self):
        """停止全局热键监听"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
            if self._listener:
                self._listener.stop()
                self._listener = None
            self._last_trigger_time.clear()
            self._pressed_modifiers.clear()
    
    def register(self, key_name: str, callback: Callable):
        """注册热键
        
        Args:
            key_name: 热键名称，如 "F10", "F12", "ctrl+s" 等
            callback: 回调函数
        """
        normalized = self._normalize_key(key_name)
        with self._lock:
            self._hotkeys[normalized] = callback
    
    def unregister(self, key_name: str):
        """取消注册热键
        
        Args:
            key_name: 热键名称
        """
        normalized = self._normalize_key(key_name)
        with self._lock:
            if normalized in self._hotkeys:
                del self._hotkeys[normalized]
    
    def update_hotkey(self, old_key: str, new_key: str, callback: Callable):
        """更新热键绑定
        
        Args:
            old_key: 旧热键
            new_key: 新热键
            callback: 回调函数
        """
        if old_key:
            self.unregister(old_key)
        if new_key:
            self.register(new_key, callback)
    
    def _normalize_key(self, key_name: str) -> str:
        """标准化热键名称
        
        Args:
            key_name: 原始热键名称
            
        Returns:
            标准化后的热键名称
        """
        if not key_name:
            return ""
        
        key_name = key_name.strip().lower()
        
        key_name = key_name.replace("<", "").replace(">", "")
        
        parts = key_name.split("+")
        parts = [p.strip() for p in parts]
        
        normalized_parts = []
        for part in parts:
            if part in ("ctrl", "control"):
                normalized_parts.append("ctrl")
            elif part in ("alt",):
                normalized_parts.append("alt")
            elif part in ("shift",):
                normalized_parts.append("shift")
            elif part in ("win", "super", "cmd", "command"):
                normalized_parts.append("cmd")
            elif part.startswith("f") and part[1:].isdigit():
                normalized_parts.append(part)
            elif len(part) == 1:
                normalized_parts.append(part)
            else:
                normalized_parts.append(part)
        
        return "+".join(sorted(normalized_parts))
    
    # 修饰键名称集合（包含 resolve_key_name 返回的各种变体）
    _MODIFIER_NAMES = {
        'ctrl', 'ctrl_l', 'ctrl_r', 'ctrlleft', 'ctrlright',
        'alt', 'alt_l', 'alt_r', 'altleft', 'altright',
        'shift', 'shift_l', 'shift_r', 'shiftleft', 'shiftright',
        'cmd', 'cmd_l', 'cmd_r', 'win', 'win_l', 'win_r'
    }
    
    @staticmethod
    def _normalize_modifier(name: str) -> str:
        """将修饰键变体统一为标准名"""
        if name in ('ctrl', 'ctrl_l', 'ctrl_r', 'ctrlleft', 'ctrlright'):
            return 'ctrl'
        elif name in ('alt', 'alt_l', 'alt_r', 'altleft', 'altright'):
            return 'alt'
        elif name in ('shift', 'shift_l', 'shift_r', 'shiftleft', 'shiftright'):
            return 'shift'
        elif name in ('cmd', 'cmd_l', 'cmd_r', 'win', 'win_l', 'win_r'):
            return 'cmd'
        return ""
    
    def _on_press(self, key):
        """按键按下事件处理"""
        try:
            from bt_utils.input_controller_factory import InputController
            if InputController.is_simulating():
                return
            
            key_name = self._get_key_name(key)
            if key_name:
                if key_name in self._MODIFIER_NAMES:
                    mod = self._normalize_modifier(key_name)
                    if mod:
                        self._pressed_modifiers.add(mod)
                else:
                    self._check_hotkey(key_name)
        except Exception:
            pass
    
    def _on_release(self, key):
        """按键释放事件处理"""
        try:
            key_name = self._get_key_name(key)
            if key_name and key_name in self._MODIFIER_NAMES:
                mod = self._normalize_modifier(key_name)
                if mod:
                    self._pressed_modifiers.discard(mod)
        except Exception:
            pass
    
    def _get_key_name(self, key) -> str:
        key_name = resolve_key_name(key)
        if not key_name:
            return None
        key_name = key_name.lower()
        if key_name.startswith('ctrl'):
            return 'ctrl'
        elif key_name.startswith('alt'):
            return 'alt'
        elif key_name.startswith('shift'):
            return 'shift'
        elif key_name.startswith('cmd') or key_name.startswith('super') or key_name == 'win':
            return 'cmd'
        return key_name
    
    def _check_hotkey(self, key_name: str):
        """检查是否触发了注册的热键
        
        支持组合键：将当前按下的修饰键与非修饰键组合，形成如 "shift+f10" 的组合键名
        
        Args:
            key_name: 按键名称（非修饰键）
        """
        # 构建组合键名：修饰键 + 当前键
        combo_parts = list(self._pressed_modifiers) + [key_name]
        combo_key = "+".join(sorted(combo_parts))
        
        # 有修饰键时只匹配组合键，无修饰键时只匹配单键，避免 Shift+F9 同时触发 F9
        if self._pressed_modifiers:
            candidates = [combo_key]
        else:
            candidates = [key_name]
        
        callback = None
        with self._lock:
            for candidate in candidates:
                if candidate in self._hotkeys:
                    current_time = time.time()
                    last_time = self._last_trigger_time.get(candidate, 0)
                    
                    if current_time - last_time < self._debounce_interval:
                        return
                    
                    self._last_trigger_time[candidate] = current_time
                    callback = self._hotkeys[candidate]
                    break
        
        if callback:
            try:
                callback()
            except Exception:
                pass
    
    def is_running(self) -> bool:
        """检查监听器是否在运行
        
        Returns:
            是否在运行
        """
        with self._lock:
            return self._running and self._listener is not None and self._listener.is_alive()
    
    def get_status(self) -> dict:
        """获取管理器状态
        
        Returns:
            状态字典
        """
        with self._lock:
            return {
                "running": self._running,
                "listener_alive": self._listener.is_alive() if self._listener else False,
                "registered_hotkeys": list(self._hotkeys.keys())
            }


def get_hotkey_manager() -> GlobalHotkeyManager:
    """获取全局热键管理器单例"""
    return GlobalHotkeyManager.get_instance()
