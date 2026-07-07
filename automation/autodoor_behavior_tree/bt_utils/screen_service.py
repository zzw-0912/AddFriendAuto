"""屏幕服务模块

提供统一的截图入口，封装全屏截图和窗口截图两种模式。
所有截图操作应通过本模块进行，避免直接调用 ImageGrab.grab()。
"""

from PIL import ImageGrab, Image
from typing import Optional, Tuple


class ScreenService:
    """屏幕截图服务

    统一的截图入口，封装底层实现细节：
    - 全屏截图：使用 PIL ImageGrab，支持多显示器
    - 窗口截图：委托给 WindowCapture（Win32 PrintWindow API）
    """

    @staticmethod
    def capture_screen(region: Tuple[int, int, int, int] = None) -> Image.Image:
        """全屏截图

        Args:
            region: 截图区域 (left, top, right, bottom)，
                    None 表示截取整个虚拟桌面

        Returns:
            PIL.Image 截图对象
        """
        if region:
            return ImageGrab.grab(bbox=region, all_screens=True)
        return ImageGrab.grab(all_screens=True)

    @staticmethod
    def capture_window(hwnd: int, region: Tuple[int, int, int, int] = None) -> Optional[Image.Image]:
        """窗口截图

        使用 Win32 PrintWindow API 截取指定窗口，
        支持窗口最小化和后台截图。

        Args:
            hwnd: 窗口句柄
            region: 窗口内的区域 (left, top, right, bottom)，
                    None 表示截取整个窗口客户区

        Returns:
            PIL.Image 截图对象，失败返回 None
        """
        from bt_utils.window_capture import WindowCapture

        if region:
            return WindowCapture.capture_window_region(hwnd, region)
        return WindowCapture.capture_window(hwnd)

    @staticmethod
    def get_virtual_screen_bounds() -> Tuple[int, int, int, int]:
        """获取虚拟屏幕边界

        代理到 screen_utils.get_virtual_screen_bounds()。

        Returns:
            Tuple[int, int, int, int]: (min_x, min_y, max_x, max_y)
        """
        from bt_utils.screen_utils import get_virtual_screen_bounds
        return get_virtual_screen_bounds()

    @staticmethod
    def get_virtual_screen_offset() -> Tuple[int, int]:
        """获取虚拟屏幕偏移量

        代理到 screen_utils.get_virtual_screen_offset()。

        Returns:
            Tuple[int, int]: (offset_x, offset_y)
        """
        from bt_utils.screen_utils import get_virtual_screen_offset
        return get_virtual_screen_offset()
