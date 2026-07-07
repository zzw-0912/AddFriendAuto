"""最终验证脚本"""
import importlib.util, sys, os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# P0: screen_utils
spec = importlib.util.spec_from_file_location('screen_utils', 'bt_utils/screen_utils.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
bounds = mod.get_virtual_screen_bounds()
offset = mod.get_virtual_screen_offset()
print(f'P0 screen_utils: bounds={bounds}, offset={offset}')
assert len(bounds) == 4 and len(offset) == 2
assert offset[0] == -bounds[0] and offset[1] == -bounds[1]
print('  P0 OK')

# P1: screen_service
spec2 = importlib.util.spec_from_file_location('screen_service', 'bt_utils/screen_service.py')
mod2 = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(mod2)
img = mod2.ScreenService.capture_screen()
print(f'P1 capture_screen: {img.size}')
assert img is not None and img.size[0] > 0
img_r = mod2.ScreenService.capture_screen(region=(0, 0, 100, 100))
print(f'P1 capture_region: {img_r.size}')
assert img_r.size == (100, 100)
b2 = mod.get_virtual_screen_bounds()  # 直接用 screen_utils 模块验证
assert b2 == bounds
print('  P1 OK')

# 旁路消除: screeninfo.get_monitors()
for fp in ['bt_utils/magnifier.py', 'bt_gui/bt_editor/property.py', 'bt_gui/widgets.py', 'bt_gui/script_tab.py']:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'screeninfo.get_monitors()' not in content, f'{fp} still has screeninfo'
print('  screeninfo bypass: OK')

# 旁路消除: ImageGrab.grab (除 screen_service.py 和 magnifier fallback)
for fp in ['bt_gui/bt_editor/property.py', 'bt_gui/widgets.py']:
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'ImageGrab.grab' not in content, f'{fp} still has ImageGrab.grab'
print('  ImageGrab bypass: OK')

# P2: context.py 使用 ScreenService
with open('bt_core/context.py', 'r', encoding='utf-8') as f:
    ctx_content = f.read()
assert 'ScreenService' in ctx_content
assert '_screenshot_manager' not in ctx_content
print('  P2 context refactor: OK')

print()
print('=== ALL PHASES PASSED ===')
