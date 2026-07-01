from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any, Tuple, Optional


class ColorConditionNode(ConditionNode):
    NODE_TYPE = "ColorConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.target_color = self._parse_color(self.config.get("target_color", None))
        self.tolerance = self.config.get_int("tolerance", 30)
        self.match_mode = self.config.get("match_mode", "any")

    def _check_condition(self, context) -> bool:
        try:
            region = self._get_effective_region(context)
            if region is None:
                self._log_condition_result(False, "请先设置检测区域")
                return False

            screenshot = self._get_region_image(context)
            if screenshot is None:
                return False

            from PIL import Image
            import numpy as np

            target_color = self._parse_color(self.config.get("target_color", None))
            tolerance = self.config.get_int("tolerance", 30)
            match_mode = self.config.get("match_mode", "any")

            img_array = np.array(screenshot)
            target = np.array(target_color)

            diff = np.abs(img_array[:, :, :3].astype(int) - target.astype(int))
            matches = np.all(diff <= tolerance, axis=2)

            if match_mode == "all":
                result = bool(np.all(matches))
            else:
                result = bool(np.any(matches))

            if result:
                match_positions = np.argwhere(matches)
                if len(match_positions) > 0:
                    center_idx = len(match_positions) // 2
                    y, x = match_positions[center_idx]
                    position = (int(x) + region[0], int(y) + region[1])
                    self._save_position(context, position)

                self._log_condition_result(True)
                return True
            else:
                self._log_condition_result(False,
                    f"未找到匹配颜色 RGB{target_color} (容差: {tolerance})")
                return False
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"ColorConditionNode '{self.name}'")
            self._log_condition_result(False, "检测异常，详情见终端日志")
            return False


