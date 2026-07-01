from .vk_mapping import vk_to_char


PYNPUT_TO_PYAUTOGUI_MAP = {
    'page_up': 'pageup',
    'page_down': 'pagedown',
    'ctrl_l': 'ctrlleft',
    'ctrl_r': 'ctrlright',
    'shift': 'shiftleft',
    'shift_l': 'shiftleft',
    'shift_r': 'shiftright',
    'alt_l': 'altleft',
    'alt_r': 'altright',
    'cmd': 'win',
    'cmd_l': 'win',
    'cmd_r': 'win',
    'win_l': 'win',
    'win_r': 'win',
    'esc': 'escape',
}


def resolve_key_name(key) -> str:
    if hasattr(key, 'char') and key.char is not None:
        if isinstance(key.char, str) and len(key.char) == 1:
            char_code = ord(key.char)
            if char_code < 32 or char_code == 127:
                if hasattr(key, 'vk') and key.vk is not None:
                    vk_char = vk_to_char(key.vk)
                    if vk_char:
                        return vk_char
            else:
                return key.char
        else:
            return key.char

    if hasattr(key, 'name') and key.name:
        return PYNPUT_TO_PYAUTOGUI_MAP.get(key.name, key.name)

    if hasattr(key, 'vk') and key.vk is not None:
        vk_char = vk_to_char(key.vk)
        if vk_char:
            return vk_char

    return None
