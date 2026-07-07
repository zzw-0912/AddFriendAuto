from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any, Tuple, Optional
from bt_utils.log_manager import LogManager
from bt_utils.ocr_manager import OCRManager
from bt_nodes.conditions.common import LANGUAGE_MAP, PREPROCESS_MODE_MAP


EXTRACT_MODE_MAP = {
    "全部": "all",
    "关键词": "keywords",
    "all": "all",
    "keywords": "keywords",
}


class TextExtractNode(ConditionNode):
    NODE_TYPE = "TextExtractNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        extract_mode_display = self.config.get("extract_mode", "全部")
        self.extract_mode = EXTRACT_MODE_MAP.get(extract_mode_display, "all")
        self.keywords = self.config.get("keywords", "")
        language_display = self.config.get("language", "简体中文")
        self.language = LANGUAGE_MAP.get(language_display, "chi_sim")
        preprocess_display = self.config.get("preprocess_mode", "默认")
        self.preprocess_mode = PREPROCESS_MODE_MAP.get(preprocess_display, "normal")
        self.output_key = self.config.get("output_key", "last_extracted_text")
        self.save_all_text = self.config.get_bool("save_all_text", False)
        self.all_text_key = self.config.get("all_text_key", "all_ocr_text")
        self.save_position = self.config.get_bool("save_position", True)
        try:
            from config.settings_manager import get_default_position_key
            default_position_key = get_default_position_key()
        except ImportError:
            default_position_key = "last_detection_position"
        position_key_value = self.config.get("position_key", "")
        self.position_key = position_key_value if position_key_value else default_position_key

    def _check_condition(self, context) -> bool:
        try:
            screenshot = self._get_region_image(context)
            if screenshot is None:
                return False

            language_display = self.config.get("language", "简体中文")
            language = LANGUAGE_MAP.get(language_display, "chi_sim")
            preprocess_display = self.config.get("preprocess_mode", "默认")
            preprocess_mode = PREPROCESS_MODE_MAP.get(preprocess_display, "normal")

            ocr_manager = OCRManager()
            all_text = ocr_manager.get_all_text(
                screenshot, language, preprocess_mode
            )

            if not all_text:
                self._log_condition_result(False, "未识别到文本")
                return False

            extract_mode_display = self.config.get("extract_mode", "全部")
            extract_mode = EXTRACT_MODE_MAP.get(extract_mode_display, "all")
            keywords = self.config.get("keywords", "")

            if extract_mode == "all":
                extracted_text = all_text
            else:
                extracted_text = self._extract_keywords_text(all_text, keywords)

            output_key = self.config.get("output_key", "last_extracted_text")
            context.blackboard.set(output_key, extracted_text)

            if self.config.get_bool("save_all_text", False):
                all_text_key = self.config.get("all_text_key", "all_ocr_text")
                context.blackboard.set(all_text_key, all_text)

            save_position = self.config.get_bool("save_position", True)
            region = self._get_effective_region(context)
            if save_position and region:
                center_x = (region[0] + region[2]) // 2
                center_y = (region[1] + region[3]) // 2
                try:
                    from config.settings_manager import get_default_position_key
                    default_position_key = get_default_position_key()
                except ImportError:
                    default_position_key = "last_detection_position"
                position_key = self.config.get("position_key", "") or default_position_key
                context.blackboard.set(position_key, (center_x, center_y))

            if extracted_text:
                self._log_condition_result(True)
                LogManager.instance().log_info(
                    node_type="文本提取节点",
                    node_name=self.name,
                    message=f"提取文本: {extracted_text[:50]}..."
                )
                return True
            else:
                self._log_condition_result(False, "未提取到匹配的文本")
                return False

        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"TextExtractNode '{self.name}'")
            self._log_condition_result(False, "执行异常，详情见终端日志")
            return False

    def _extract_keywords_text(self, all_text: str, keywords: str) -> str:
        lines = all_text.split('\n')
        matched_lines = []

        for line in lines:
            line = line.strip()
            if line and keywords in line:
                matched_lines.append(line)

        return '\n'.join(matched_lines)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextExtractNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node
