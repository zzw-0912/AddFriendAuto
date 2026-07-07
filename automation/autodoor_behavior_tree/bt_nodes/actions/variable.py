from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any
from bt_utils.log_manager import LogManager


class SetVariableNode(ActionNode):
    NODE_TYPE = "SetVariableNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.variable_name = self.config.get("variable_name", "")
        self.value = self.config.get("value", "")
        self.operation = self.config.get("operation", "set")

    def _execute_action(self, context):
        var_name = self.config.get("variable_name", "")
        operation = self.config.get("operation", "set")

        if not var_name:
            LogManager.instance().log_failure(
                node_type="变量节点",
                node_name=self.name,
                reason="未配置变量名"
            )
            return NodeStatus.FAILURE

        if operation == "set":
            value_type = self.config.get("value_type", "constant")
            if value_type == "variable":
                source_var = self.config.get("source_variable", "")
                if source_var:
                    value = context.blackboard.get(source_var)
                    if value is None:
                        LogManager.instance().log_failure(
                            node_type="变量节点",
                            node_name=self.name,
                            reason=f"来源变量 '{source_var}' 不存在或值为 None"
                        )
                        return NodeStatus.FAILURE
                else:
                    LogManager.instance().log_failure(
                        node_type="变量节点",
                        node_name=self.name,
                        reason="未配置来源变量"
                    )
                    return NodeStatus.FAILURE
            else:
                raw_value = self.config.get("value", "")
                value = self._parse_value(raw_value)
            context.blackboard.set(var_name, value)
            LogManager.instance().log_success(
                node_type="变量节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        elif operation == "increment":
            current = context.blackboard.get(var_name)
            if current is None:
                LogManager.instance().log_failure(
                    node_type="变量节点",
                    node_name=self.name,
                    reason=f"变量 '{var_name}' 不存在"
                )
                return NodeStatus.FAILURE
            try:
                new_value = current + 1
                context.blackboard.set(var_name, new_value)
                LogManager.instance().log_success(
                    node_type="变量节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            except TypeError:
                LogManager.instance().log_failure(
                    node_type="变量节点",
                    node_name=self.name,
                    reason=f"变量 '{var_name}' 的值 {current} 无法递增"
                )
                return NodeStatus.FAILURE

        elif operation == "delete":
            context.blackboard.delete(var_name)
            LogManager.instance().log_success(
                node_type="变量节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        else:
            LogManager.instance().log_failure(
                node_type="变量节点",
                node_name=self.name,
                reason=f"未知操作: {operation}"
            )
            return NodeStatus.FAILURE

    @staticmethod
    def _parse_value(raw: str):
        if raw.lower() == "true":
            return True
        if raw.lower() == "false":
            return False
        if raw.lower() == "none":
            return None
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        return raw

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SetVariableNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.variable_name = config.get("variable_name", "")
        node.value = config.get("value", "")
        node.operation = config.get("operation", "set")
        return node
