"""DPI感知初始化工具

必须在导入任何GUI库(如customtkinter/tkinter)之前调用。
"""
import ctypes
import sys


def initialize_dpi_awareness():
    """初始化进程的DPI感知模式
    
    调用顺序：必须在此进程中所有其他操作之前执行，
    包括tkinter/customtkinter的导入。
    
    优先级：
    1. Per-Monitor V2 (Windows 10 1703+) — 推荐
    2. Per-Monitor V1 (Windows 8.1+) — 备选
    3. System-DPI-Aware (Windows Vista+) — 兼容备选
    
    Returns:
        str: 实际设置的DPI感知模式名称
    """
    if sys.platform != 'win32':
        return "Non-Windows"
    
    try:
        ctypes.windll.shcore.SetProcessDpiAwarenessContext(-4)
        return "Per-Monitor V2"
    except (AttributeError, OSError):
        pass
    
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "Per-Monitor V1"
    except (AttributeError, OSError):
        pass
    
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return "System-DPI-Aware"
    except (AttributeError, OSError):
        pass
    
    return "Unaware (fallback)"


def get_dpi_scale():
    if sys.platform != 'win32':
        return 1.0
    
    try:
        h = ctypes.windll.user32.MonitorFromWindow(0, 1)
        x = ctypes.c_uint()
        y = ctypes.c_uint()
        ctypes.windll.shcore.GetDpiForMonitor(h, 0, ctypes.byref(x), ctypes.byref(y))
        if x.value > 0:
            return x.value / 96.0
    except Exception:
        pass
    
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi > 0:
            return dpi / 96.0
    except Exception:
        pass
    
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        if hdc:
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            return dpi / 96.0
    except Exception:
        pass
    
    return 1.0


def get_window_dpi_scale(hwnd):
    """获取指定窗口所在显示器的DPI缩放比例
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        float: DPI缩放比例
    """
    if sys.platform != 'win32':
        return 1.0
    
    try:
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
        if dpi > 0:
            return dpi / 96.0
    except Exception:
        pass
    
    return get_dpi_scale()
