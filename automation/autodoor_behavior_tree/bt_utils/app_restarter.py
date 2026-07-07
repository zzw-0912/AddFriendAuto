import ctypes
import sys
import os


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def is_dd_available() -> bool:
    possible_paths = []
    base_path = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    possible_paths.extend([
        os.path.join(os.path.dirname(base_path), "drivers", "DD64.dll"),
        os.path.join(base_path, "..", "drivers", "DD64.dll"),
        os.path.join(base_path, "drivers", "DD64.dll"),
        os.path.join(base_path, "DD64.dll"),
    ])
    return any(os.path.exists(p) for p in possible_paths)


def is_ib_available() -> bool:
    """检测 IbInputSimulator.dll 是否存在"""
    possible_paths = []
    base_path = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    possible_paths.extend([
        os.path.join(os.path.dirname(base_path), "drivers", "IbInputSimulator.dll"),
        os.path.join(base_path, "..", "drivers", "IbInputSimulator.dll"),
        os.path.join(base_path, "drivers", "IbInputSimulator.dll"),
        os.path.join(base_path, "IbInputSimulator.dll"),
    ])
    return any(os.path.exists(p) for p in possible_paths)


def get_recommended_method() -> str:
    """根据可用驱动推荐最优引擎

    优先级：ib > dd > pyautogui
    后台模式需要用户主动选择，不在自动推荐范围内。

    Returns:
        推荐的输入方式 key
    """
    if is_ib_available():
        return "ib"
    if is_dd_available():
        return "dd"
    return "pyautogui"


def _get_restart_command():
    if is_frozen():
        exe_path = sys.executable
        params = " ".join(sys.argv[1:])
        return exe_path, params
    else:
        exe_path = sys.executable
        script_path = os.path.abspath(sys.argv[0])
        params = f'"{script_path}"'
        if len(sys.argv) > 1:
            params += " " + " ".join(f'"{a}"' for a in sys.argv[1:])
        return exe_path, params


def restart_as_admin() -> bool:
    exe_path, params = _get_restart_command()
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe_path,
        params,
        None,
        1
    )
    if ret <= 32:
        return False
    return True


def restart_normal():
    exe_path, params = _get_restart_command()
    if is_frozen():
        os.execv(exe_path, [exe_path] + sys.argv[1:])
    else:
        import subprocess
        subprocess.Popen([exe_path] + sys.argv)


def restart_app(as_admin: bool = False) -> bool:
    if as_admin:
        if is_admin():
            restart_normal()
            return True
        success = restart_as_admin()
        if success:
            return True
        return False
    else:
        restart_normal()
        return True
