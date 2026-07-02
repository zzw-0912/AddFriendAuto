"""屏幕工具模块

提供虚拟屏幕边界计算和偏移量获取的统一实现，
支持多显示器环境，内置三级 fallback 策略。
"""

from typing import Tuple, Optional
import threading


_virtual_screen_bounds_cache: Optional[Tuple[int, int, int, int]] = None
_cache_lock = threading.Lock()


def get_virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """获取虚拟桌面边界（支持多显示器）

    三级 fallback 策略：
    1. screeninfo 库（最精确）
    2. Win32 API GetSystemMetrics(76-79)（次精确）
    3. 固定默认值 (0, 0, 1920, 1080)（兜底）

    Returns:
        Tuple[int, int, int, int]: (min_x, min_y, max_x, max_y)
    """
    global _virtual_screen_bounds_cache

    if _virtual_screen_bounds_cache is not None:
        return _virtual_screen_bounds_cache

    bounds = _compute_virtual_screen_bounds()

    with _cache_lock:
        _virtual_screen_bounds_cache = bounds

    return bounds


def get_virtual_screen_offset() -> Tuple[int, int]:
    """获取虚拟桌面的左上角偏移量

    多屏时副显示器可能在主显示器左侧或上方，
    此时 min_x/min_y 为负值，偏移量为其相反数。

    Returns:
        Tuple[int, int]: (offset_x, offset_y)
        多屏时为正值（表示需要补偿的偏移），单屏时为 (0, 0)
    """
    min_x, min_y, _, _ = get_virtual_screen_bounds()
    return (-min_x, -min_y)


def invalidate_cache() -> None:
    """清除虚拟屏幕边界缓存

    在显示器配置变更时调用（如热插拔显示器）。
    """
    global _virtual_screen_bounds_cache
    with _cache_lock:
        _virtual_screen_bounds_cache = None


def _compute_virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """实际计算虚拟屏幕边界（内部方法）"""
    # 策略1: screeninfo 库
    try:
        import screeninfo
        monitors = screeninfo.get_monitors()
        if monitors:
            return (
                min(m.x for m in monitors),
                min(m.y for m in monitors),
                max(m.x + m.width for m in monitors),
                max(m.y + m.height for m in monitors),
            )
    except ImportError:
        pass
    except Exception:
        pass

    # 策略2: Win32 API
    try:
        import ctypes
        user32 = ctypes.windll.user32
        virtual_left = user32.GetSystemMetrics(76)
        virtual_top = user32.GetSystemMetrics(77)
        virtual_width = user32.GetSystemMetrics(78)
        virtual_height = user32.GetSystemMetrics(79)
        if virtual_width > 0 and virtual_height > 0:
            return (
                virtual_left,
                virtual_top,
                virtual_left + virtual_width,
                virtual_top + virtual_height,
            )
    except Exception:
        pass

    # 策略3: 默认值
    return (0, 0, 1920, 1080)
