import ctypes
from ctypes import Structure, c_wchar, c_ushort, c_ulong, c_long
from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from bt_utils.log_manager import LogManager
from typing import Dict, Any


class DEVMODE(Structure):
    _fields_ = [
        ("dmDeviceName", c_wchar * 32),
        ("dmSpecVersion", c_ushort),
        ("dmDriverVersion", c_ushort),
        ("dmSize", c_ushort),
        ("dmDriverExtra", c_ushort),
        ("dmFields", c_ulong),
        ("dmPositionX", c_long),
        ("dmPositionY", c_long),
        ("dmDisplayOrientation", c_ulong),
        ("dmDisplayFixedOutput", c_ulong),
        ("dmColor", c_ushort),
        ("dmDuplex", c_ushort),
        ("dmYResolution", c_ushort),
        ("dmTTOption", c_ushort),
        ("dmCollate", c_ushort),
        ("dmFormName", c_wchar * 32),
        ("dmLogPixels", c_ushort),
        ("dmBitsPerPel", c_ulong),
        ("dmPelsWidth", c_ulong),
        ("dmPelsHeight", c_ulong),
        ("dmDisplayFlags", c_ulong),
        ("dmDisplayFrequency", c_ulong),
        ("dmICMMethod", c_ulong),
        ("dmICMIntent", c_ulong),
        ("dmMediaType", c_ulong),
        ("dmDitherType", c_ulong),
        ("dmReserved1", c_ulong),
        ("dmReserved2", c_ulong),
        ("dmPanningWidth", c_ulong),
        ("dmPanningHeight", c_ulong),
    ]


class SetDisplayNode(ActionNode):
    NODE_TYPE = "SetDisplayNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self._done = False

    def _execute_action(self, context) -> NodeStatus:
        if self._done:
            return NodeStatus.SUCCESS

        w = self.config.get_int("width", 1920)
        h = self.config.get_int("height", 1080)

        user32 = ctypes.windll.user32

        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        user32.EnumDisplaySettingsW(0, -1, ctypes.byref(dm))

        dm.dmPelsWidth = w
        dm.dmPelsHeight = h
        dm.dmFields = 0x00080000 | 0x00100000

        result = user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0)

        if result == 0:
            self._done = True
            LogManager.instance().log_success(
                node_type="设置分辨率",
                node_name=self.name,
                message=f"{w}x{h}"
            )
            return NodeStatus.SUCCESS
        else:
            LogManager.instance().log_failure(
                node_type="设置分辨率",
                node_name=self.name,
                reason=f"失败, 错误码: {result}"
            )
            return NodeStatus.FAILURE

    def abort(self, context) -> None:
        ctypes.windll.user32.ChangeDisplaySettingsW(0, 0)
        super().abort(context)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetDisplayNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        return cls(node_id=data.get("id"), config=config)

