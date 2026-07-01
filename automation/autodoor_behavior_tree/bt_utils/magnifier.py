import tkinter as tk
from PIL import Image, ImageGrab, ImageTk
from typing import Optional, Tuple


class MagnifierWindow:
    """放大镜窗口组件"""
    
    def __init__(
        self,
        zoom_factor: int = 4,
        size: int = 150,
        show_crosshair: bool = True,
        show_color_info: bool = True
    ):
        """
        初始化放大镜
        
        Args:
            zoom_factor: 放大倍数（默认4倍）
            size: 放大镜窗口大小（默认150x150像素）
            show_crosshair: 是否显示十字准线
            show_color_info: 是否显示颜色信息
        """
        self.zoom_factor = zoom_factor
        self.size = size
        self.show_crosshair = show_crosshair
        self.show_color_info = show_color_info
        
        self.window: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.info_label: Optional[tk.Label] = None
        self.last_screenshot: Optional[Image.Image] = None
        self.photo = None
        
        self._virtual_screen_bounds = None
    
    def _get_virtual_screen_bounds(self) -> Tuple[int, int, int, int]:
        """获取虚拟桌面边界（支持多显示器）"""
        if self._virtual_screen_bounds is not None:
            return self._virtual_screen_bounds
        from bt_utils.screen_utils import get_virtual_screen_bounds
        self._virtual_screen_bounds = get_virtual_screen_bounds()
        return self._virtual_screen_bounds
        
    def show(self, x: int, y: int):
        """
        在指定位置显示放大镜
        
        Args:
            x: 鼠标X坐标
            y: 鼠标Y坐标
        """
        if self.window is not None:
            return
        
        self.window = tk.Toplevel()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        
        canvas_size = self.size
        info_height = 70 if self.show_color_info else 0
        
        self.window.geometry(f"{canvas_size}x{canvas_size + info_height}")
        
        self.canvas = tk.Canvas(
            self.window,
            width=canvas_size,
            height=canvas_size,
            bg="#000000",
            highlightthickness=0
        )
        self.canvas.pack()
        
        if self.show_color_info:
            self.info_label = tk.Label(
                self.window,
                text="",
                font=("Consolas", 9),
                bg="#2b2b2b",
                fg="#ffffff",
                anchor="w",
                padx=5,
                pady=2,
                justify="left",
                highlightthickness=0
            )
            self.info_label.pack(fill="x", expand=False)
        
        self.update(x, y)
    
    def update(self, x: int, y: int):
        """
        更新放大镜显示内容
        
        Args:
            x: 鼠标X坐标（虚拟桌面坐标）
            y: 鼠标Y坐标（虚拟桌面坐标）
        """
        if self.window is None or self.canvas is None:
            return
        
        min_x, min_y, max_x, max_y = self._get_virtual_screen_bounds()
        virtual_width = max_x - min_x
        virtual_height = max_y - min_y
        
        window_x = x + 20
        window_y = y + 20
        
        if window_x + self.size > max_x:
            window_x = x - self.size - 20
        if window_y + self.size > max_y:
            window_y = y - self.size - 20
        
        if window_x < min_x:
            window_x = min_x + 5
        if window_y < min_y:
            window_y = min_y + 5
        
        self.window.geometry(f"+{window_x}+{window_y}")
        
        capture_size = self.size // self.zoom_factor
        half_capture = capture_size // 2
        
        left = x - half_capture
        top = y - half_capture
        right = x + half_capture
        bottom = y + half_capture
        
        try:
            from bt_utils.screen_service import ScreenService
            screenshot = ScreenService.capture_screen(region=(left, top, right, bottom))
        except Exception:
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
        
        self.last_screenshot = screenshot
        
        enlarged = screenshot.resize(
            (self.size, self.size),
            Image.Resampling.NEAREST
        )
        
        self.photo = ImageTk.PhotoImage(enlarged)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        
        if self.show_crosshair:
            center = self.size // 2
            self.canvas.create_line(
                center, 0, center, self.size,
                fill="#ff0000", width=1, dash=(2, 2)
            )
            self.canvas.create_line(
                0, center, self.size, center,
                fill="#ff0000", width=1, dash=(2, 2)
            )
        
        if self.show_color_info and self.info_label:
            pixel = screenshot.getpixel((half_capture, half_capture))
            if isinstance(pixel, int):
                r, g, b = pixel, pixel, pixel
            elif len(pixel) == 4:
                r, g, b, a = pixel
            else:
                r, g, b = pixel[:3]
            
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            
            info_text = f"坐标: ({x}, {y})\n颜色: {hex_color}\nRGB({r}, {g}, {b})"
            self.info_label.config(text=info_text)
    
    def hide(self):
        """隐藏放大镜窗口"""
        if self.window is not None:
            self.window.destroy()
            self.window = None
            self.canvas = None
            self.info_label = None
            self.last_screenshot = None
            self.photo = None
