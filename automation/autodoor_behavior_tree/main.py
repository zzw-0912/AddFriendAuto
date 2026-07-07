import sys
import os
import traceback

LOG_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "autodoor_behavior_tree")
try:
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception:
    LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, "startup_error.log")

def write_log(msg):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"[{timestamp}] {msg}\n")
    except Exception:
        pass

write_log("=== Application startup begin ===")
write_log(f"Python version: {sys.version}")
write_log(f"Working directory: {os.getcwd()}")
write_log(f"sys.executable: {sys.executable}")
write_log(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'Not set')}")

def setup_error_logging():
    def exception_hook(exctype, value, tb):
        error_msg = ''.join(traceback.format_exception(exctype, value, tb))
        write_log(f"EXCEPTION: {error_msg}")
        print(f"STARTUP ERROR - Log file: {LOG_FILE}")
        print(error_msg)
        sys.__excepthook__(exctype, value, tb)
    
    sys.excepthook = exception_hook
    return LOG_FILE

LOG_FILE_RESULT = setup_error_logging()
print(f"Error logging initialized. Log file: {LOG_FILE}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

write_log("Importing dpi_awareness...")
try:
    from bt_utils.dpi_awareness import initialize_dpi_awareness
    initialize_dpi_awareness()
    write_log("dpi_awareness initialized successfully")
except Exception as e:
    write_log(f"DPI awareness initialization failed: {e}")
    traceback.print_exc()

write_log("Importing json and logging...")
import json
import logging
write_log("json and logging imported successfully")

def get_resource_path(relative_path):
    """获取资源文件的绝对路径，支持PyInstaller打包后的路径"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

def load_version():
    """从build_info.json加载版本信息"""
    build_info_file = get_resource_path('bt_utils/build_info.json')
    
    if os.path.exists(build_info_file):
        try:
            with open(build_info_file, 'r', encoding='utf-8') as f:
                build_info = json.load(f)
                return build_info.get('version', '1.0.0')
        except Exception:
            pass
    
    return "1.2.2a"

def load_github_info():
    """从build_info.json加载GitHub仓库信息"""
    build_info_file = get_resource_path('bt_utils/build_info.json')
    
    if os.path.exists(build_info_file):
        try:
            with open(build_info_file, 'r', encoding='utf-8') as f:
                build_info = json.load(f)
                github = build_info.get('github', {})
                return github.get('owner', 'wdhq4261761'), github.get('repo', 'autodoor_behavior_tree')
        except Exception:
            pass
    
    return 'wdhq4261761', 'autodoor_behavior_tree'

VERSION = load_version()
write_log(f"Version loaded: {VERSION}")

write_log("Importing version_checker...")
from bt_utils.version_checker import BetaExpirationChecker
write_log("version_checker imported successfully")

beta_checker = BetaExpirationChecker()
if beta_checker.check_expiration():
    write_log("Beta expiration detected, showing dialog")
    beta_checker.show_expiration_dialog()
    sys.exit(0)

write_log("Importing customtkinter...")
import customtkinter as ctk
write_log("customtkinter imported successfully")

write_log("Importing BehaviorTreeApp...")
from bt_gui.app import BehaviorTreeApp
write_log("BehaviorTreeApp imported successfully")

write_log("Importing registry...")
from bt_core.registry import register_all_nodes
write_log("registry imported successfully")


def ensure_workspace_exists():
    """确保workspace文件夹存在"""
    from config.settings_manager import SettingsManager
    
    settings_manager = SettingsManager()
    saved_path = settings_manager.get("default_project_path", "")
    
    if saved_path and os.path.exists(saved_path):
        return
    
    workspace_dir = SettingsManager.get_default_workspace_path()
    
    try:
        os.makedirs(workspace_dir, exist_ok=True)
    except Exception:
        pass


def check_vcredist():
    """检查 Visual C++ Redistributable 运行时库"""
    try:
        import onnxruntime
        return True
    except ImportError as e:
        if "DLL load failed" in str(e) or "onnxruntime_pybind11_state" in str(e):
            return False
        raise
    except Exception:
        return False


def initialize_ocr():
    """初始化OCR引擎"""
    try:
        if not check_vcredist():
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            
            messagebox.showwarning(
                "缺少运行时库",
                "程序检测到缺少 Visual C++ Redistributable 运行时库。\n\n"
                "OCR 相关功能将无法使用。\n\n"
                "请下载并安装：\n"
                "https://aka.ms/vs/17/release/vc_redist.x64.exe\n\n"
                "安装后重启程序即可使用 OCR 功能。\n\n"
                "其他功能不受影响，可正常使用。"
            )
            
            root.destroy()
            
            from bt_utils.ocr_manager import OCRManager
            OCRManager.set_unavailable("缺少 Visual C++ Redistributable 运行时库")
            
            return False
        
        from bt_utils.ocr_manager import OCRManager
        OCRManager.initialize()
        return True
        
    except Exception as e:
        from bt_utils.ocr_manager import OCRManager
        OCRManager.set_unavailable(str(e))
        
        return False


def initialize_input():
    """初始化输入控制器"""
    try:
        from bt_utils.input_controller_factory import InputController
        InputController()
        return True
    except Exception:
        return False


def check_admin_for_driver(method: str, display_name: str, is_available_fn):
    """检查驱动模式是否需要管理员权限，如需要则提权重启

    Args:
        method: 输入方式 key（如 "dd", "ib"）
        display_name: 显示名称（如 "DD虚拟键盘", "IbInputSimulator"）
        is_available_fn: 检测 DLL 是否存在的函数
    """
    from config.settings_manager import SettingsManager
    from bt_utils.app_restarter import is_admin, restart_as_admin

    settings = SettingsManager.get_instance()
    kb_method = settings.get("input.keyboard_method", "pyautogui")
    ms_method = settings.get("input.mouse_method", "pyautogui")

    # 键盘或鼠标任一使用该驱动都需要管理员权限
    if kb_method != method and ms_method != method:
        return True

    if not is_available_fn():
        write_log(f"{display_name} DLL not found, falling back to PyAutoGUI")
        if kb_method == method:
            settings.set("input.keyboard_method", "pyautogui")
        if ms_method == method:
            settings.set("input.mouse_method", "pyautogui")
        return True

    if is_admin():
        write_log(f"{display_name}: already running as admin")
        return True

    write_log(f"{display_name}: not admin, requesting elevation")

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()

    result = messagebox.askyesno(
        "需要管理员权限",
        f"{display_name}需要管理员权限才能正常工作。\n\n"
        "是否以管理员身份重新启动应用？\n\n"
        "点击「否」将使用 PyAutoGUI 模式启动。",
        icon='warning'
    )
    root.destroy()

    if result:
        success = restart_as_admin()
        if success:
            write_log("Admin restart initiated, exiting current process")
            sys.exit(0)
        else:
            write_log("Admin restart failed (UAC denied or error)")
            root2 = tk.Tk()
            root2.withdraw()
            messagebox.showwarning(
                "权限获取失败",
                "无法获取管理员权限，将使用 PyAutoGUI 模式启动。"
            )
            root2.destroy()

    write_log("Falling back to PyAutoGUI mode")
    if kb_method == method:
        settings.set("input.keyboard_method", "pyautogui")
    if ms_method == method:
        settings.set("input.mouse_method", "pyautogui")
    return True


def main():
    ensure_workspace_exists()

    from bt_utils.app_restarter import is_dd_available, is_ib_available
    check_admin_for_driver("dd", "DD虚拟键盘", is_dd_available)
    check_admin_for_driver("ib", "IbInputSimulator", is_ib_available)
    
    initialize_ocr()
    initialize_input()
    
    register_all_nodes()
    
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = BehaviorTreeApp()
    
    from bt_utils.version_checker import VersionChecker
    github_owner, github_repo = load_github_info()
    version_checker = VersionChecker(
        app=app,
        owner=github_owner,
        repo=github_repo,
        current_version=VERSION
    )
    
    app._version_checker = version_checker
    
    version_checker.check_force_update()
    
    version_checker.start_auto_check(app)
    
    app.mainloop()


if __name__ == "__main__":
    main()
