"""快速验证脚本 - 每个重构阶段完成后运行"""

import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verify_p0():
    """P0 阶段验证: screen_utils.py"""
    print("=" * 50)
    print("P0: 验证 screen_utils.py")
    print("=" * 50)

    try:
        from bt_utils.screen_utils import get_virtual_screen_bounds, get_virtual_screen_offset
        bounds = get_virtual_screen_bounds()
        offset = get_virtual_screen_offset()

        print(f"  虚拟屏幕边界: {bounds}")
        print(f"  虚拟屏幕偏移: {offset}")

        assert len(bounds) == 4, "边界应为4元组"
        assert len(offset) == 2, "偏移应为2元组"
        assert bounds[0] <= bounds[2], "min_x <= max_x"
        assert bounds[1] <= bounds[3], "min_y <= max_y"
        assert offset[0] == -bounds[0], "offset_x == -min_x"
        assert offset[1] == -bounds[1], "offset_y == -min_y"

        print("  ✅ P0 验证通过")
        return True
    except Exception as e:
        print(f"  ❌ P0 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_p1():
    """P1 阶段验证: ScreenService"""
    print("=" * 50)
    print("P1: 验证 ScreenService")
    print("=" * 50)

    try:
        from bt_utils.screen_service import ScreenService
        from bt_utils.screenshot import ScreenshotManager

        img = ScreenService.capture_screen()
        assert img is not None, "全屏截图不应为 None"
        print(f"  全屏截图: {img.size}")

        img_region = ScreenService.capture_screen(region=(0, 0, 100, 100))
        assert img_region.size == (100, 100), "区域截图大小应为100x100"
        print(f"  区域截图: {img_region.size}")

        mgr = ScreenshotManager()
        img2 = mgr.get_full_screenshot()
        assert img2 is not None, "ScreenshotManager 应正常工作"
        print(f"  ScreenshotManager: {img2.size}")

        print("  ✅ P1 验证通过")
        return True
    except Exception as e:
        print(f"  ❌ P1 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_p2():
    """P2 阶段验证: ExecutionContext"""
    print("=" * 50)
    print("P2: 验证 ExecutionContext")
    print("=" * 50)

    try:
        from bt_core.context import ExecutionContext

        ctx = ExecutionContext()
        img = ctx.get_screenshot()
        assert img is not None, "全屏截图不应为 None"
        print(f"  全屏截图: {img.size}")

        img_region = ctx.get_screenshot((0, 0, 50, 50))
        assert img_region is not None, "区域截图不应为 None"
        print(f"  区域截图: {img_region.size}")

        print("  ✅ P2 验证通过")
        return True
    except Exception as e:
        print(f"  ❌ P2 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_imports():
    """验证所有模块正常导入"""
    print("=" * 50)
    print("导入验证")
    print("=" * 50)

    modules = [
        'bt_utils.screen_utils',
        'bt_utils.screen_service',
        'bt_utils.screenshot',
        'bt_utils.magnifier',
        'bt_utils.proxies',
        'bt_core.context',
    ]

    all_ok = True
    for mod in modules:
        try:
            __import__(mod)
            print(f"  ✅ {mod}")
        except Exception as e:
            print(f"  ❌ {mod}: {e}")
            all_ok = False

    return all_ok


def verify_no_direct_screeninfo():
    """验证不再有直接的 screeninfo.get_monitors() 调用"""
    print("=" * 50)
    print("旁路消除验证")
    print("=" * 50)

    files_to_check = [
        ('bt_utils/magnifier.py', 'bt_utils.magnifier'),
        ('bt_gui/bt_editor/property.py', 'bt_gui.bt_editor.property'),
        ('bt_gui/widgets.py', 'bt_gui.widgets'),
        ('bt_gui/script_tab.py', 'bt_gui.script_tab'),
    ]

    all_ok = True
    for filepath, module_name in files_to_check:
        try:
            with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath), 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查是否还有 screeninfo.get_monitors() 调用
            if 'screeninfo.get_monitors()' in content:
                print(f"  ❌ {filepath}: 仍存在 screeninfo.get_monitors() 调用")
                all_ok = False
            else:
                print(f"  ✅ {filepath}: 无直接 screeninfo 调用")
        except Exception as e:
            print(f"  ⚠️ {filepath}: 无法检查 ({e})")

    return all_ok


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"

    results = {}

    if phase in ("p0", "all"):
        results["P0"] = verify_p0()

    if phase in ("p1", "all"):
        results["P1"] = verify_p1()

    if phase in ("p2", "all"):
        results["P2"] = verify_p2()

    results["imports"] = verify_imports()

    if phase in ("p0", "all"):
        results["no_bypass"] = verify_no_direct_screeninfo()

    print("\n" + "=" * 50)
    print("总结")
    print("=" * 50)
    for name, ok in results.items():
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)
