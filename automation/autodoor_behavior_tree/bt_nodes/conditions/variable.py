from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any


class VariableConditionNode(ConditionNode):
    NODE_TYPE = "VariableConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.variable_name = self.config.get("variable_name", "")
        self.comparison = self.config.get("comparison") or self.config.get("operator", "==")
        self.target_value = self.config.get("target_value") or self.config.get("compare_value", "")

    def _check_condition(self, context):
        var_name = self.config.get("variable_name", "")
        operator = self.config.get("operator", "==")

        if not var_name:
            self._log_condition_result(False, "未设置变量名")
            return False

        if operator == "exists":
            result = context.blackboard.exists(var_name)
            self._log_condition_result(result, f"变量 '{var_name}' 存在性检查: {result}")
            return result

        if operator == "not_exists":
            result = not context.blackboard.exists(var_name)
            self._log_condition_result(result, f"变量 '{var_name}' 不存在检查: {result}")
            return result

        current_value = context.blackboard.get(var_name)
        if current_value is None:
            self._log_condition_result(False, f"变量 '{var_name}' 不存在")
            return False

        compare_type = self.config.get("compare_type", "constant")
        if compare_type == "variable":
            compare_var = self.config.get("compare_variable", "")
            if compare_var:
                target_value = context.blackboard.get(compare_var)
                if target_value is None:
                    self._log_condition_result(False,
                        f"比较变量 '{compare_var}' 不存在或值为 None")
                    return False
            else:
                self._log_condition_result(False, "未配置比较变量")
                return False
        else:
            raw_value = self.config.get("compare_value", "")
            target_value = self._parse_value(raw_value)

        result = self._compare_value(current_value, operator, target_value)
        self._log_condition_result(result,
            f"变量 '{var_name}'({current_value}) {operator} {target_value}: {result}")
        return result

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

    def _compare_value(self, value, comparison: str, target_value) -> bool:
        try:
            ops = {
                ">": lambda a, b: a > b,
                ">=": lambda a, b: a >= b,
                "<": lambda a, b: a < b,
                "<=": lambda a, b: a <= b,
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
            }

            if comparison in ops:
                try:
                    num_value = float(value) if isinstance(value, str) else value
                    num_target = float(target_value) if isinstance(target_value, str) else target_value

                    if isinstance(num_value, (int, float)) and isinstance(num_target, (int, float)):
                        return ops[comparison](num_value, num_target)
                except (ValueError, TypeError):
                    pass

            str_value = str(value)
            str_target = str(target_value)

            if comparison == "==":
                return str_value == str_target
            elif comparison == "!=":
                return str_value != str_target
            elif comparison == "contains":
                return str_target in str_value
            elif comparison == "not_contains":
                return str_target not in str_value
            elif comparison == "starts_with":
                return str_value.startswith(str_target)
            elif comparison == "ends_with":
                return str_value.endswith(str_target)
            else:
                return str_value == str_target
        except Exception:
            return False
