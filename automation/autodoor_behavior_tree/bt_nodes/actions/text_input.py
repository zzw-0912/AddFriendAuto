import time
import os
import random
import pyperclip
from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any, List
from bt_utils.log_manager import LogManager


INPUT_MODE_MAP = {
    "文本提取值": "extracted",
    "预设文本": "preset",
    "文件": "file",
    "extracted": "extracted",
    "preset": "preset",
    "file": "file",
}

EXECUTION_MODE_MAP = {
    "顺序": "sequential",
    "随机": "random",
    "sequential": "sequential",
    "random": "random",
}


class TextInputNode(ActionNode):
    NODE_TYPE = "TextInputNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        input_mode_display = self.config.get("input_mode", "文本提取值")
        self.input_mode = INPUT_MODE_MAP.get(input_mode_display, "extracted")
        self.preset_texts: List[str] = self.config.get("preset_texts", [])
        execution_mode_display = self.config.get("execution_mode", "顺序")
        self.execution_mode = EXECUTION_MODE_MAP.get(execution_mode_display, "sequential")
        self.blackboard_key = self.config.get("blackboard_key", "last_extracted_text")
        self.file_path = self.config.get("file_path", "")
        self.input_delay = self.config.get_int("input_delay", 0)
        self.clear_before_input = self.config.get_bool("clear_before_input", False)
        self.save_input_text = self.config.get_bool("save_input_text", False)
        self.output_key = self.config.get("output_key", "last_input_text")

    def _execute_action(self, context) -> NodeStatus:
        try:
            text = self._get_text(context)
            if not text:
                LogManager.instance().log_failure(
                    node_type="文本输入节点",
                    node_name=self.name,
                    reason="未获取到文本内容"
                )
                return NodeStatus.FAILURE

            if self.config.get_bool("clear_before_input", False):
                context.execute_key_press("ctrl", "down", 0)
                context.execute_key_press("a", "press", 0)
                context.execute_key_press("ctrl", "up", 0)
                time.sleep(0.1)

            self._input_text(context, text)

            if self.config.get_bool("save_input_text", False):
                context.blackboard.set(self.config.get("output_key", "last_input_text"), text)

            LogManager.instance().log_success(
                node_type="文本输入节点",
                node_name=self.name
            )

            return NodeStatus.SUCCESS

        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"TextInputNode '{self.name}'")
            LogManager.instance().log_failure(
                node_type="文本输入节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE

    def _get_text(self, context) -> str:
        input_mode = INPUT_MODE_MAP.get(self.config.get("input_mode", "文本提取值"), "extracted")
        if input_mode == "preset":
            preset_texts = self.config.get("preset_texts", [])
            if not preset_texts:
                return ""
            execution_mode = EXECUTION_MODE_MAP.get(self.config.get("execution_mode", "顺序"), "sequential")
            if execution_mode == "sequential":
                return self._get_next_preset_text(context, preset_texts)
            else:
                return self._get_random_preset_text(preset_texts)

        elif input_mode == "extracted":
            return context.blackboard.get(self.config.get("blackboard_key", "last_extracted_text"), "")

        elif input_mode == "file":
            return self._read_file(context)

        return ""

    def _get_next_preset_text(self, context, preset_texts: List[str]) -> str:
        index_key = f"{self.node_id}_text_index"
        current_index = context.blackboard.get(index_key, 0)

        text = preset_texts[current_index % len(preset_texts)]

        next_index = (current_index + 1) % len(preset_texts)
        context.blackboard.set(index_key, next_index)

        return text

    def _get_random_preset_text(self, preset_texts: List[str]) -> str:
        selected_index = random.randint(0, len(preset_texts) - 1)
        return preset_texts[selected_index]

    def _read_file(self, context) -> str:
        file_path = self.config.get("file_path", "")
        if not file_path:
            return ""

        if not os.path.isabs(file_path):
            file_path = context.resolve_path(file_path)

        if not os.path.exists(file_path):
            LogManager.instance().log_failure(
                node_type="文本输入节点",
                node_name=self.name,
                reason=f"文件不存在: {self.config.get('file_path', '')}"
            )
            return ""
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _input_text(self, context, text: str) -> None:
        import pyautogui

        original_pause = pyautogui.PAUSE
        pyautogui.PAUSE = 0

        try:
            if self.config.get_int("input_delay", 0) == 0:
                self._input_text_fast(context, text)
            else:
                self._input_text_slow(context, text)
        finally:
            pyautogui.PAUSE = original_pause
    
    def _input_text_fast(self, context, text: str) -> None:
        pyperclip.copy(text)
        time.sleep(0.01)
        
        context.execute_key_press("ctrl", "down", 0)
        context.execute_key_press("v", "press", 0)
        context.execute_key_press("ctrl", "up", 0)
    
    def _input_text_slow(self, context, text: str) -> None:
        CLIPBOARD_READY_DELAY = 0.005
        PASTE_COMPLETE_DELAY = 0.01
        
        for char in text:
            if not context.check_running():
                break

            if char == "\n":
                context.execute_key_press("enter", "press", 0)
                time.sleep(PASTE_COMPLETE_DELAY)
            elif char == "\t":
                context.execute_key_press("tab", "press", 0)
                time.sleep(PASTE_COMPLETE_DELAY)
            else:
                pyperclip.copy(char)
                time.sleep(CLIPBOARD_READY_DELAY)
                
                context.execute_key_press("ctrl", "down", 0)
                context.execute_key_press("v", "press", 0)
                context.execute_key_press("ctrl", "up", 0)
                
                time.sleep(PASTE_COMPLETE_DELAY)

            time.sleep(self.config.get_int("input_delay", 0) / 1000.0)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextInputNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node
