from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any, Tuple, Optional
from bt_utils.ocr_manager import OCRManager
from bt_nodes.conditions.common import LANGUAGE_MAP, PREPROCESS_MODE_MAP


class NumberConditionNode(ConditionNode):
    NODE_TYPE = "NumberConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.comparison = self.config.get("compare_mode", ">=")
        self.target_value = self.config.get_float("threshold", 0)
        self.extract_mode = self.config.get("extract_mode", "无规则")
        self.extract_pattern = self.config.get("extract_pattern", "")
        self.min_confidence = self.config.get_float("min_confidence", 50) / 100.0
        self.value_key = self.config.get("value_key", "last_number_value")
        
        self.search_direction = self.config.get("search_direction", "左上")
        
        language_display = self.config.get("language", "简体中文")
        self.language = LANGUAGE_MAP.get(language_display, "chi_sim")
        preprocess_display = self.config.get("preprocess_mode", "默认")
        self.preprocess_mode = PREPROCESS_MODE_MAP.get(preprocess_display, "normal")

    def _check_condition(self, context) -> bool:
        try:
            region = self._get_effective_region(context)
            if region is None:
                self._log_condition_result(False, "请先设置检测区域")
                return False

            screenshot = self._get_region_image(context)
            if screenshot is None:
                return False

            from bt_utils.direction import SearchDirection
            search_direction = self.config.get("search_direction", "左上")
            direction = SearchDirection.VALUE_MAP.get(search_direction, SearchDirection.TOP_LEFT)

            language_display = self.config.get("language", "简体中文")
            language = LANGUAGE_MAP.get(language_display, "chi_sim")
            preprocess_display = self.config.get("preprocess_mode", "默认")
            preprocess_mode = PREPROCESS_MODE_MAP.get(preprocess_display, "normal")
            extract_mode = self.config.get("extract_mode", "无规则")
            extract_pattern = self.config.get("extract_pattern", "")
            min_confidence = self.config.get_float("min_confidence", 50) / 100.0

            success, value, all_text, position = OCRManager().recognize_number_with_position(
                screenshot,
                language=language,
                preprocess_mode=preprocess_mode,
                extract_mode=extract_mode,
                extract_pattern=extract_pattern,
                min_confidence=min_confidence,
                search_direction=direction
            )

            if not success or value is None:
                self._log_condition_result(False, f"无法识别数字 (文本: {all_text})")
                return False

            if position:
                actual_position = (position[0] + region[0], position[1] + region[1])
                self._save_position(context, actual_position)

            value_key = self.config.get("value_key", "last_number_value")
            context.blackboard.set("last_number_value", value)
            if value_key and value_key != "last_number_value":
                context.blackboard.set(value_key, value)

            comparison = self.config.get("compare_mode", ">=")
            target_value = self.config.get_float("threshold", 0)
            result = self._compare_value(value, comparison, target_value)

            if result:
                self._log_condition_result(True, extra_info=f"值: {value}")
                return True
            else:
                self._log_condition_result(False,
                    f"数值比较失败: {value} {comparison} {target_value}")
                return False
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"NumberConditionNode '{self.name}'")
            self._log_condition_result(False, "检测异常，详情见终端日志")
            return False

    def _compare_value(self, value: float, comparison: str, target_value: float) -> bool:
        ops = {
            ">": lambda a, b: a > b,
            ">=": lambda a, b: a >= b,
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
        }
        op = ops.get(comparison, lambda a, b: False)
        return op(value, target_value)
