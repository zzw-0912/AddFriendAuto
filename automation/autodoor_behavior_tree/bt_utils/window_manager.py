import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, List, Dict

user32 = ctypes.windll.user32


class WindowManager:
    @staticmethod
    def enum_all_windows() -> List[Tuple[int, str]]:
        results = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buffer = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buffer, length + 1)
                    title = buffer.value
                    if title:
                        results.append((hwnd, title))
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return results

    @staticmethod
    def find_window_by_title(keyword: str) -> Optional[int]:
        windows = WindowManager.enum_all_windows()
        for hwnd, title in windows:
            if keyword.lower() in title.lower():
                return hwnd
        return None

    @staticmethod
    def find_window_by_pid(pid: int) -> Optional[int]:
        results = []

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_windows_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                if window_pid.value == pid:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buffer, length + 1)
                        if buffer.value:
                            results.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        
        if results:
            return results[0]
        return None

    @staticmethod
    def find_window_by_pid_and_title(pid: int, title_keyword: str) -> Optional[int]:
        windows = WindowManager.enum_all_windows()
        for hwnd, title in windows:
            window_pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if window_pid.value == pid and title_keyword.lower() in title.lower():
                return hwnd
        return None

    @staticmethod
    def find_main_window_by_pid(pid: int) -> Optional[int]:
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        results = []

        def enum_windows_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                if window_pid.value == pid:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buffer, length + 1)
                        if buffer.value:
                            style = user32.GetWindowLongW(hwnd, -16)
                            ex_style = user32.GetWindowLongW(hwnd, -20)
                            
                            WS_OVERLAPPEDWINDOW = 0x00CF0000
                            WS_EX_TOOLWINDOW = 0x00000080
                            WS_EX_APPWINDOW = 0x00040000
                            
                            is_main = bool(style & WS_OVERLAPPEDWINDOW)
                            is_app_window = bool(ex_style & WS_EX_APPWINDOW)
                            is_tool_window = bool(ex_style & WS_EX_TOOLWINDOW)
                            
                            rect = wintypes.RECT()
                            user32.GetClientRect(hwnd, ctypes.byref(rect))
                            area = max(0, (rect.right - rect.left)) * max(0, (rect.bottom - rect.top))
                            
                            results.append({
                                'hwnd': hwnd,
                                'area': area,
                                'is_main': is_main,
                                'is_app_window': is_app_window,
                                'is_tool_window': is_tool_window,
                                'title': buffer.value,
                            })
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        
        if not results:
            return None
        
        results.sort(key=lambda x: (
            not x['is_tool_window'],
            x['is_app_window'],
            x['is_main'],
            x['area']
        ), reverse=True)
        
        return results[0]['hwnd']

    @staticmethod
    def find_all_windows_by_pid(pid: int) -> List[int]:
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        results = []

        def enum_windows_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                window_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                if window_pid.value == pid:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buffer, length + 1)
                        if buffer.value:
                            results.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)
        return results

    @staticmethod
    def get_window_pid(hwnd: int) -> Optional[int]:
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value if pid.value else None
        except Exception:
            return None

    @staticmethod
    def find_window_smart(pid: Optional[int], title_keyword: str) -> Tuple[Optional[int], str]:
        if pid and title_keyword:
            hwnd = WindowManager.find_window_by_pid_and_title(pid, title_keyword)
            if hwnd:
                return hwnd, "pid_title"
        elif pid:
            hwnd = WindowManager.find_main_window_by_pid(pid)
            if hwnd:
                return hwnd, "pid"
        
        if title_keyword:
            hwnd = WindowManager.find_window_by_title(title_keyword)
            if hwnd:
                return hwnd, "title"
        
        return None, "not_found"

    @staticmethod
    def find_window_smart_with_hwnd(hwnd: int, pid: Optional[int], title_keyword: str) -> Tuple[Optional[int], str]:
        if hwnd and WindowManager.is_window_valid(hwnd):
            if title_keyword:
                actual_title = WindowManager.get_window_title(hwnd)
                if actual_title and title_keyword.lower() in actual_title.lower():
                    return hwnd, "hwnd"
            else:
                return hwnd, "hwnd"
        
        if pid and title_keyword:
            hwnd_found = WindowManager.find_window_by_pid_and_title(pid, title_keyword)
            if hwnd_found:
                return hwnd_found, "pid_title"
        elif pid:
            hwnd_found = WindowManager.find_main_window_by_pid(pid)
            if hwnd_found:
                return hwnd_found, "pid"
        
        if title_keyword:
            hwnd_found = WindowManager.find_window_by_title(title_keyword)
            if hwnd_found:
                return hwnd_found, "title"
        
        return None, "not_found"

    @staticmethod
    def get_window_title(hwnd: int) -> str:
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                return buffer.value
            return ""
        except Exception:
            return ""

    @staticmethod
    def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        return None

    @staticmethod
    def is_foreground_window(hwnd: int) -> bool:
        try:
            return user32.GetForegroundWindow() == hwnd
        except Exception:
            return False

    @staticmethod
    def get_foreground_window() -> Optional[int]:
        try:
            return user32.GetForegroundWindow()
        except Exception:
            return None

    @staticmethod
    def set_foreground_window(hwnd: int) -> bool:
        return WindowManager.switch_to_window(hwnd)

    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        try:
            return bool(user32.IsWindow(hwnd))
        except Exception:
            return False

    @staticmethod
    def save_foreground_window() -> int:
        return user32.GetForegroundWindow()

    @staticmethod
    def switch_to_window(hwnd: int) -> bool:
        try:
            SW_RESTORE = 9
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001

            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)

            target_thread = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_thread))
            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
            attached = False
            if target_thread.value != current_thread:
                attached = user32.AttachThreadInput(current_thread, target_thread.value, True)

            user32.SetWindowPos(
                hwnd, HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE
            )

            user32.SetForegroundWindow(hwnd)

            user32.SetWindowPos(
                hwnd, HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE
            )

            if attached:
                user32.AttachThreadInput(current_thread, target_thread.value, False)

            return True
        except Exception:
            return False

    @staticmethod
    def restore_window(saved_hwnd: int) -> bool:
        try:
            VK_MENU = 0x12
            VK_TAB = 0x09
            KEYEVENTF_KEYUP = 0x0002

            user32.keybd_event(VK_MENU, 0, 0, 0)
            user32.keybd_event(VK_TAB, 0, 0, 0)
            user32.keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

            if WindowManager.is_window_valid(saved_hwnd):
                user32.SetForegroundWindow(saved_hwnd)

            return True
        except Exception:
            return False

    @staticmethod
    def get_window_at_point(x: int, y: int) -> Optional[int]:
        """获取指定屏幕坐标处的窗口句柄

        从光标下的子控件逐级向上查找，返回最近的有标题的顶层窗口。
        同一应用的不同子窗口也能返回不同句柄。
        """
        try:
            point = wintypes.POINT(x, y)
            hwnd = user32.WindowFromPoint(point)
            if not hwnd:
                return None

            current = hwnd
            visited = set()
            while current and current not in visited:
                visited.add(current)
                length = user32.GetWindowTextLengthW(current)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(current, buf, 256)
                    cls = buf.value
                    if cls not in ("Progman", "WorkerW", "SysListView32", "Shell_TrayWnd"):
                        return current
                current = user32.GetAncestor(current, 1)  # GA_PARENT

            return None
        except Exception:
            return None

    @staticmethod
    def get_window_info(hwnd: int) -> dict:
        """获取窗口的完整信息（标题、PID、类名）"""
        title = WindowManager.get_window_title(hwnd)
        pid = WindowManager.get_window_pid(hwnd)
        class_name = ""
        try:
            buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buffer, 256)
            class_name = buffer.value
        except Exception:
            pass
        return {"hwnd": hwnd, "title": title, "pid": pid, "class_name": class_name}

    @staticmethod
    def get_cursor_pos() -> Tuple[int, int]:
        """获取当前光标在屏幕上的坐标"""
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    @staticmethod
    def is_left_button_pressed() -> bool:
        """检测鼠标左键是否按下"""
        VK_LBUTTON = 0x01
        return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

    @staticmethod
    def is_escape_pressed() -> bool:
        """检测 ESC 键是否按下"""
        VK_ESCAPE = 0x1B
        return bool(user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
