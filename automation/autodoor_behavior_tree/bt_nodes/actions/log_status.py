from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any
from bt_utils.log_manager import LogManager


class LogStatusNode(ActionNode):
    NODE_TYPE = "LogStatusNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)

    def _execute_action(self, context) -> NodeStatus:
        target = self.parent

        if target is None:
            LogManager.instance().log_info(
                node_type="日志状态",
                node_name=self.name,
                message="无连接节点"
            )
            return NodeStatus.SUCCESS

        target_name = getattr(target, 'name', target.NODE_TYPE)

        if target.status == NodeStatus.SUCCESS:
            LogManager.instance().log_success(
                node_type="日志状态",
                node_name=self.name,
                message=f"'{target_name}' 执行成功"
            )
        elif target.status == NodeStatus.FAILURE:
            LogManager.instance().log_failure(
                node_type="日志状态",
                node_name=self.name,
                reason=f"'{target_name}' 执行失败"
            )
        else:
            LogManager.instance().log_info(
                node_type="日志状态",
                node_name=self.name,
                message=f"'{target_name}' 结果: {target.status.value}"
            )

        return NodeStatus.SUCCESS

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogStatusNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node
