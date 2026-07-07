from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any
from bt_utils.log_manager import LogManager


class MouseScrollNode(ActionNode):
    NODE_TYPE = "MouseScrollNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.distance = self.config.get_int("distance", 5)
        self.clicks = self.config.get_int("clicks", 1)
        self.direction = self.config.get("direction", "向上")

    def _execute_action(self, context) -> NodeStatus:
        try:
            distance = self.config.get_int("distance", 5)
            clicks = self.config.get_int("clicks", 1)
            direction = self.config.get("direction", "向上")

            scroll_distance = distance

            if direction == "向上":
                scroll_distance = abs(distance)
            elif direction == "向下":
                scroll_distance = -abs(distance)
            elif direction == "向左":
                scroll_distance = -abs(distance)
            elif direction == "向右":
                scroll_distance = abs(distance)

            for click_num in range(clicks):
                # ★ 检查是否应该停止（F12或超时后）
                if not context.is_running:
                    print(f"[MouseScroll] ⚠️ 检测到停止信号，中断第{click_num+1}/{clicks}次点击")
                    break

                context.execute_mouse_scroll(scroll_distance)
            
            LogManager.instance().log_success(
                node_type="鼠标滚轮节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS
                
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"MouseScrollNode '{self.name}'")
            LogManager.instance().log_failure(
                node_type="鼠标滚轮节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MouseScrollNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.distance = config.get_int("distance", 5)
        node.clicks = config.get_int("clicks", 1)
        node.direction = config.get("direction", "向上")
        return node
