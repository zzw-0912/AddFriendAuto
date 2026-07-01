from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any, Tuple, Optional
from PIL import Image
import os
from bt_utils.image_processor import ImageProcessor


class ImageConditionNode(ConditionNode):
    NODE_TYPE = "ImageConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.template_path = self.config.get("template_path", "")
        raw_threshold = self.config.get_float("threshold", 80)
        self.threshold = raw_threshold / 100.0 if raw_threshold > 1 else raw_threshold

    def _check_condition(self, context) -> bool:
        try:
            resolved_path = self._resolve_template_path(context)
            if resolved_path is None:
                return False

            screenshot = self._get_region_image(context)
            if screenshot is None:
                return False

            template_path = self.config.get("template_path", "")
            if not os.path.exists(resolved_path):
                self._log_condition_result(False, f"模板文件不存在: {template_path}")
                return False

            template = Image.open(resolved_path)
            if template is None:
                self._log_condition_result(False, f"无法加载模板文件: {template_path}")
                return False

            ratio = self._get_dpi_scale_ratio()
            if ratio != 1.0:
                new_w = max(1, int(template.width * ratio))
                new_h = max(1, int(template.height * ratio))
                template = template.resize((new_w, new_h), Image.LANCZOS)

            raw_threshold = self.config.get_float("threshold", 80)
            threshold = raw_threshold / 100.0 if raw_threshold > 1 else raw_threshold

            found, position, confidence = ImageProcessor.find_template(
                screenshot, template, threshold
            )

            if found:
                actual_position = self._adjust_position(position, context)
                self._save_position(context, actual_position)
                self._log_condition_result(True)
                return True
            else:
                self._log_condition_result(False, f"未找到匹配模板 (阈值: {threshold}, 最高置信度: {confidence:.2f})")
                return False
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"ImageConditionNode '{self.name}'")
            self._log_condition_result(False, "检测异常，详情见终端日志")
            return False

    def _resolve_template_path(self, context) -> Optional[str]:
        """解析模板路径

        Args:
            context: 执行上下文

        Returns:
            解析后的绝对路径，或None
        """
        template_path = self.config.get("template_path", "")
        if not template_path:
            self._log_condition_result(False, "未设置模板路径")
            return None

        if template_path.startswith("./") and hasattr(context, 'resolve_path'):
            return context.resolve_path(template_path)

        return template_path

    def _adjust_position(self, position: tuple, context=None) -> tuple:
        """调整坐标（加上区域偏移）

        Args:
            position: 相对位置
            context: 执行上下文

        Returns:
            绝对位置
        """
        if position is None:
            return None
        region = self._get_effective_region(context) if context else self._parse_region(self.config.get("region", None))
        if region:
            return (position[0] + region[0], position[1] + region[1])
        return position


