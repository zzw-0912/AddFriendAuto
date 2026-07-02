"""
后台消息输入控制器实现

通过 Win32 PostMessage/SendMessage 向目标窗口发送消息，
实现后台操作（窗口无需置前）。
"""
import ctypes
import time
from typing import Optional, Tuple

from .base_input import BaseInputController, InputLevel
from .dd_input import VK_CODE_MAP
from .log_manager import LogManager


# Win32 消息常量
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_RBUTTONDBLCLK = 0x0206
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MBUTTONDBLCLK = 0x0209
WM_MOUSEWHEEL = 0x020A
WM_MOUSEHWHEEL = 0x020E

# 鼠标虚拟键标志
MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_MBUTTON = 0x0010

user32 = ctypes.windll.user32


def _make_lparam(x: int, y: int) -> int:
    """构造 LPARAM：低16位为X，高16位为Y"""
    return (y << 16) | (x & 0xFFFF)


class BackgroundInputController(BaseInputController):
    """后台消息输入控制器

    通过 PostMessage 向目标窗口发送 Win32 消息，
    实现后台鼠标/键盘操作，窗口无需置前。
    """

    def __init__(self, hwnd: int = 0):
        self._hwnd = hwnd
        self._available = hwnd != 0

    @classmethod
    def get_input_level(cls) -> InputLevel:
        return InputLevel.BACKGROUND

    @classmethod
    def is_driver_available(cls) -> bool:
        """后台消息始终可用（Win32 API）"""
        return True

    def set_target_window(self, hwnd: int) -> None:
        """设置目标窗口句柄"""
        self._hwnd = hwnd
        self._available = hwnd != 0

    def get_target_window(self) -> Optional[int]:
        """获取目标窗口句柄"""
        return self._hwnd if self._available else None

    @property
    def is_available(self) -> bool:
        return self._available and self._hwnd != 0

    def get_name(self) -> str:
        return "后台消息"

    def _log(self, message: str):
        LogManager.debug_print(f"[BG] {message}")

    def _get_vk_code(self, key: str) -> int:
        """获取 Windows VK 码"""
        key_lower = key.lower()
        vk_code = VK_CODE_MAP.get(key_lower)
        if vk_code is None:
            if len(key_lower) == 1 and key_lower.isalpha():
                vk_code = ord(key_lower.upper())
        return vk_code or 0

    def key_press(self, key: str, action: str = "press", duration: int = 0) -> None:
        """后台按键操作"""
        if not self._available:
            self._log(f"key_press SKIP: not available (hwnd={self._hwnd})")
            return

        vk_code = self._get_vk_code(key)
        if vk_code == 0:
            self._log(f"key_press SKIP: unknown key '{key}'")
            return

        self._log(f"key_press: hwnd={self._hwnd:#x}, key={key}(vk=0x{vk_code:02X}), action={action}")

        if action == "press":
            user32.PostMessageW(self._hwnd, WM_KEYDOWN, vk_code, 0)
            if duration > 0:
                time.sleep(duration / 1000.0)
            user32.PostMessageW(self._hwnd, WM_KEYUP, vk_code, 0)
        elif action == "down":
            user32.PostMessageW(self._hwnd, WM_KEYDOWN, vk_code, 0)
        elif action == "up":
            user32.PostMessageW(self._hwnd, WM_KEYUP, vk_code, 0)

    def key_down(self, key: str) -> None:
        if not self._available:
            return
        vk_code = self._get_vk_code(key)
        if vk_code:
            user32.PostMessageW(self._hwnd, WM_KEYDOWN, vk_code, 0)

    def key_up(self, key: str) -> None:
        if not self._available:
            return
        vk_code = self._get_vk_code(key)
        if vk_code:
            user32.PostMessageW(self._hwnd, WM_KEYUP, vk_code, 0)

    def mouse_click(self, button: str = "left", position: Tuple[int, int] = None,
                   action: str = "press", duration: int = 0) -> None:
        """后台鼠标点击"""
        if not self._available:
            self._log(f"mouse_click SKIP: not available (hwnd={self._hwnd})")
            return

        x = position[0] if position else 0
        y = position[1] if position else 0
        lparam = _make_lparam(x, y)

        self._log(f"mouse_click: hwnd={self._hwnd:#x}, button={button}, pos=({x}, {y}), action={action}, lparam=0x{lparam:08X}")

        msg_down_map = {
            "left": WM_LBUTTONDOWN,
            "right": WM_RBUTTONDOWN,
            "middle": WM_MBUTTONDOWN,
        }
        msg_up_map = {
            "left": WM_LBUTTONUP,
            "right": WM_RBUTTONUP,
            "middle": WM_MBUTTONUP,
        }
        wparam_flag_map = {
            "left": MK_LBUTTON,
            "right": MK_RBUTTON,
            "middle": MK_MBUTTON,
        }

        if action == "press":
            # 先移动鼠标
            user32.PostMessageW(self._hwnd, WM_MOUSEMOVE, 0, lparam)
            # 按下
            user32.PostMessageW(self._hwnd, msg_down_map.get(button, WM_LBUTTONDOWN),
                              wparam_flag_map.get(button, MK_LBUTTON), lparam)
            if duration > 0:
                time.sleep(duration / 1000.0)
            # 释放
            user32.PostMessageW(self._hwnd, msg_up_map.get(button, WM_LBUTTONUP), 0, lparam)
        elif action == "down":
            user32.PostMessageW(self._hwnd, WM_MOUSEMOVE, 0, lparam)
            user32.PostMessageW(self._hwnd, msg_down_map.get(button, WM_LBUTTONDOWN),
                              wparam_flag_map.get(button, MK_LBUTTON), lparam)
        elif action == "up":
            user32.PostMessageW(self._hwnd, msg_up_map.get(button, WM_LBUTTONUP), 0, lparam)

    def mouse_down(self, button: str = "left") -> None:
        """按下鼠标（在当前位置）"""
        if not self._available:
            return
        msg_map = {"left": WM_LBUTTONDOWN, "right": WM_RBUTTONDOWN, "middle": WM_MBUTTONDOWN}
        wparam_map = {"left": MK_LBUTTON, "right": MK_RBUTTON, "middle": MK_MBUTTON}
        user32.PostMessageW(self._hwnd, msg_map.get(button, WM_LBUTTONDOWN),
                          wparam_map.get(button, MK_LBUTTON), 0)

    def mouse_up(self, button: str = "left") -> None:
        """释放鼠标"""
        if not self._available:
            return
        msg_map = {"left": WM_LBUTTONUP, "right": WM_RBUTTONUP, "middle": WM_MBUTTONUP}
        user32.PostMessageW(self._hwnd, msg_map.get(button, WM_LBUTTONUP), 0, 0)

    def mouse_move(self, position: Tuple[int, int], relative: bool = False) -> None:
        """后台鼠标移动"""
        if not self._available:
            self._log(f"mouse_move SKIP: not available (hwnd={self._hwnd})")
            return

        if relative:
            # 获取当前光标位置，加上偏移量，计算绝对坐标
            point = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            abs_x = point.x + position[0]
            abs_y = point.y + position[1]
            # 转换为客户区坐标
            client_x = ctypes.c_long(abs_x)
            client_y = ctypes.c_long(abs_y)
            user32.ScreenToClient(self._hwnd, ctypes.byref(client_x))
            user32.ScreenToClient(self._hwnd, ctypes.byref(client_y))
            lparam = _make_lparam(client_x.value, client_y.value)
            self._log(f"mouse_move: relative=({position[0]},{position[1]}), "
                      f"screen=({abs_x},{abs_y}), client=({client_x.value},{client_y.value})")
        else:
            lparam = _make_lparam(position[0], position[1])
            self._log(f"mouse_move: hwnd={self._hwnd:#x}, pos=({position[0]}, {position[1]}), lparam=0x{lparam:08X}")

        user32.PostMessageW(self._hwnd, WM_MOUSEMOVE, 0, lparam)

    def mouse_scroll(self, amount: int, position: Tuple[int, int] = None) -> None:
        """后台鼠标滚轮"""
        if not self._available:
            return

        x = position[0] if position else 0
        y = position[1] if position else 0
        lparam = _make_lparam(x, y)
        # WM_MOUSEWHEEL 的 wParam 高位为 delta，低位为按键标志
        delta = amount * 120  # WHEEL_DELTA = 120
        wparam = (delta << 16) & 0xFFFFFFFF
        # WM_MOUSEWHEEL 需要使用屏幕坐标的 lParam
        # 但 PostMessage 到窗口时使用客户区坐标
        user32.PostMessageW(self._hwnd, WM_MOUSEWHEEL, wparam, lparam)
