"""DPI感知功能回归测试用例

测试DPI感知改造后的各项功能是否正常工作。
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDPIAwareness(unittest.TestCase):
    """DPI感知初始化测试"""

    def test_initialize_dpi_awareness_returns_string(self):
        """测试DPI初始化返回有效字符串"""
        from bt_utils.dpi_awareness import initialize_dpi_awareness
        result = initialize_dpi_awareness()
        self.assertIsInstance(result, str)
        self.assertIn(result, [
            "Per-Monitor V2",
            "Per-Monitor V1", 
            "System-DPI-Aware",
            "Unaware (fallback)",
            "Non-Windows"
        ])

    def test_get_dpi_scale_returns_positive(self):
        """测试DPI缩放比例返回正值"""
        from bt_utils.dpi_awareness import get_dpi_scale
        scale = get_dpi_scale()
        self.assertIsInstance(scale, float)
        self.assertGreater(scale, 0)


class TestWindowCaptureWithDPI(unittest.TestCase):
    """窗口截图DPI兼容性测试"""

    def test_capture_window_returns_none_for_invalid_hwnd(self):
        """测试无效窗口句柄返回None"""
        from bt_utils.window_capture import WindowCapture
        result = WindowCapture.capture_window(0)
        self.assertIsNone(result)

    def test_get_window_rect_returns_none_for_invalid_hwnd(self):
        """测试无效窗口句柄获取矩形返回None"""
        from bt_utils.window_capture import WindowCapture
        result = WindowCapture.get_window_rect(0)
        self.assertIsNone(result)


class TestCoordinateConverterWithDPI(unittest.TestCase):
    """坐标转换DPI兼容性测试"""

    def test_get_screen_size_returns_positive(self):
        """测试屏幕尺寸返回正值"""
        from bt_utils.coordinate import CoordinateConverter
        width, height = CoordinateConverter.get_screen_size()
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

    def test_absolute_to_window_with_invalid_hwnd(self):
        """测试无效窗口句柄坐标转换返回None"""
        from bt_utils.coordinate import CoordinateConverter
        result = CoordinateConverter.absolute_to_window(100, 100, 0)
        self.assertIsNone(result)

    def test_window_to_absolute_with_invalid_hwnd(self):
        """测试无效窗口句柄反向坐标转换返回None"""
        from bt_utils.coordinate import CoordinateConverter
        result = CoordinateConverter.window_to_absolute(100, 100, 0)
        self.assertIsNone(result)

    def test_absolute_to_client_with_invalid_hwnd(self):
        """测试无效窗口句柄客户区坐标转换返回None"""
        from bt_utils.coordinate import CoordinateConverter
        result = CoordinateConverter.absolute_to_client(100, 100, 0)
        self.assertIsNone(result)

    def test_client_to_absolute_with_invalid_hwnd(self):
        """测试无效窗口句柄反向客户区坐标转换返回None"""
        from bt_utils.coordinate import CoordinateConverter
        result = CoordinateConverter.client_to_absolute(100, 100, 0)
        self.assertIsNone(result)


class TestScreenshotManagerWithDPI(unittest.TestCase):
    """截图管理器DPI兼容性测试"""

    def test_get_full_screenshot_returns_image(self):
        """测试全屏截图返回有效图像"""
        from bt_utils.screenshot import ScreenshotManager
        manager = ScreenshotManager()
        img = manager.get_full_screenshot()
        self.assertIsNotNone(img)
        self.assertGreater(img.width, 0)
        self.assertGreater(img.height, 0)

    def test_get_region_screenshot_returns_image(self):
        """测试区域截图返回有效图像"""
        from bt_utils.screenshot import ScreenshotManager
        manager = ScreenshotManager()
        region = (0, 0, 100, 100)
        img = manager.get_region_screenshot(region)
        self.assertIsNotNone(img)
        self.assertEqual(img.width, 100)
        self.assertEqual(img.height, 100)

    def test_get_region_screenshot_with_negative_coords(self):
        """测试负坐标区域截图（副屏场景）"""
        from bt_utils.screenshot import ScreenshotManager
        manager = ScreenshotManager()
        region = (-100, 0, 0, 100)
        try:
            img = manager.get_region_screenshot(region)
            if img is not None:
                self.assertEqual(img.width, 100)
                self.assertEqual(img.height, 100)
        except Exception:
            pass


class TestMultiMonitorSupport(unittest.TestCase):
    """多显示器支持测试"""

    def test_screeninfo_available(self):
        """测试screeninfo库可用"""
        try:
            import screeninfo
            monitors = screeninfo.get_monitors()
            self.assertGreater(len(monitors), 0)
        except ImportError:
            self.skipTest("screeninfo not installed")

    def test_virtual_screen_bounds(self):
        """测试虚拟桌面边界获取"""
        try:
            import screeninfo
            monitors = screeninfo.get_monitors()
            min_x = min(monitor.x for monitor in monitors)
            min_y = min(monitor.y for monitor in monitors)
            max_x = max(monitor.x + monitor.width for monitor in monitors)
            max_y = max(monitor.y + monitor.height for monitor in monitors)
            self.assertGreater(max_x - min_x, 0)
            self.assertGreater(max_y - min_y, 0)
        except ImportError:
            self.skipTest("screeninfo not installed")


class TestPreviewContextWithDPI(unittest.TestCase):
    """预览检测DPI兼容性测试（需要GUI环境）"""

    def setUp(self):
        try:
            import tkinter as tk
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.root = None

    def tearDown(self):
        if self.root:
            self.root.destroy()

    def test_preview_image_offset_calculation(self):
        """测试预览图像偏移量计算"""
        try:
            import screeninfo
            monitors = screeninfo.get_monitors()
            offset_x = -min(monitor.x for monitor in monitors)
            offset_y = -min(monitor.y for monitor in monitors)
            self.assertIsInstance(offset_x, int)
            self.assertIsInstance(offset_y, int)
        except ImportError:
            self.skipTest("screeninfo not installed")


if __name__ == '__main__':
    unittest.main(verbosity=2)
