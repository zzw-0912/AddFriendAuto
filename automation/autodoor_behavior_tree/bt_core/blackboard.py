from typing import Any, Dict, List, Callable
import threading


class Blackboard:
    """黑板系统 - 节点间数据共享

    提供节点间的数据共享机制，支持订阅/通知模式。
    线程安全实现，使用可重入锁保护数据访问。

    Attributes:
        BUILTIN_VARS: 内置变量默认值
    """
    BUILTIN_VARS = {
        "last_detection_position": None,
        "last_detection_x": None,
        "last_detection_y": None,
        "last_number_value": None,
    }

    BUILTIN_VAR_DISPLAY_NAMES = {
        "last_detection_position": "最近检测点",
        "last_detection_x": "最近检测点x值",
        "last_detection_y": "最近检测点y值",
        "last_number_value": "最近数字值",
    }

    @classmethod
    def get_builtin_vars_info(cls) -> Dict[str, str]:
        result = dict(cls.BUILTIN_VAR_DISPLAY_NAMES)
        try:
            from config.settings_manager import get_blackboard_config
            config = get_blackboard_config()
            config_mapping = {
                config.default_position_key: "最近检测点",
                config.default_value_key: "最近数字值",
            }
            for key, display_name in config_mapping.items():
                if key not in result:
                    result[key] = display_name
        except ImportError:
            pass
        return result

    def __init__(self):
        self._data: Dict[str, Any] = dict(self.BUILTIN_VARS)
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def get(self, key: str, default: Any = None) -> Any:
        """获取变量值

        Args:
            key: 变量名
            default: 默认值

        Returns:
            变量值
        """
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置变量值

        Args:
            key: 变量名
            value: 变量值
        """
        with self._lock:
            old_value = self._data.get(key)
            self._data[key] = value
            subscribers = self._subscribers.get(key, [])[:] if key in self._subscribers else []

        for callback in subscribers:
            try:
                callback(old_value, value)
            except Exception:
                pass

    def increment(self, key: str, amount=1) -> None:
        """递增变量

        Args:
            key: 变量名
            amount: 递增量
        """
        with self._lock:
            old_value = self._data.get(key)
            current = self._data.get(key, 0)
            if not isinstance(current, (int, float)):
                try:
                    current = float(current)
                except (ValueError, TypeError):
                    current = 0
            if not isinstance(amount, (int, float)):
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    amount = 1
            new_value = current + amount
            if isinstance(new_value, float) and new_value == int(new_value):
                new_value = int(new_value)
            self._data[key] = new_value
            subscribers = self._subscribers.get(key, [])[:] if key in self._subscribers else []

        for callback in subscribers:
            try:
                callback(old_value, new_value)
            except Exception:
                pass

    def delete(self, key: str) -> None:
        """删除变量

        Args:
            key: 变量名
        """
        with self._lock:
            if key in self._data and key not in self.BUILTIN_VARS:
                del self._data[key]

    def exists(self, key: str) -> bool:
        """检查变量是否存在

        Args:
            key: 变量名

        Returns:
            是否存在
        """
        with self._lock:
            return key in self._data

    def clear(self) -> None:
        """清空黑板（保留内置变量）"""
        with self._lock:
            self._data = dict(self.BUILTIN_VARS)

    def subscribe(self, key: str, callback: Callable[[Any, Any], None]) -> None:
        """订阅变量变化

        Args:
            key: 变量名
            callback: 回调函数 (old_value, new_value)
        """
        with self._lock:
            if key not in self._subscribers:
                self._subscribers[key] = []
            self._subscribers[key].append(callback)

    def unsubscribe(self, key: str, callback: Callable = None) -> None:
        """取消订阅

        Args:
            key: 变量名
            callback: 回调函数，为None时取消所有订阅
        """
        with self._lock:
            if key not in self._subscribers:
                return

            if callback is None:
                del self._subscribers[key]
            elif callback in self._subscribers[key]:
                self._subscribers[key].remove(callback)

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典

        Returns:
            字典表示
        """
        with self._lock:
            return dict(self._data)

    def from_dict(self, data: Dict[str, Any]) -> None:
        """从字典导入

        Args:
            data: 字典数据
        """
        with self._lock:
            self._data.update(data)

    def get_all_keys(self) -> List[str]:
        """获取所有变量名

        Returns:
            变量名列表
        """
        with self._lock:
            return list(self._data.keys())

    def get_snapshot(self) -> Dict[str, Any]:
        """获取黑板数据快照

        Returns:
            数据快照
        """
        with self._lock:
            return dict(self._data)


class NamespacedBlackboard:
    """命名空间黑板代理

    自动为所有键添加命名空间前缀，实现子树黑板隔离。
    对使用者透明，get("x") 实际读写 parent["namespace.x"]
    """

    def __init__(self, parent: Blackboard, namespace: str):
        self._parent = parent
        self._namespace = namespace
        self._prefix = f"{namespace}."

    def _wrap_key(self, key: str) -> str:
        """添加命名空间前缀"""
        if key.startswith(self._prefix):
            return key
        return f"{self._prefix}{key}"

    def get(self, key: str, default: Any = None) -> Any:
        return self._parent.get(self._wrap_key(key), default)

    def set(self, key: str, value: Any) -> None:
        self._parent.set(self._wrap_key(key), value)

    def increment(self, key: str, amount: int = 1) -> None:
        self._parent.increment(self._wrap_key(key), amount)

    def delete(self, key: str) -> None:
        self._parent.delete(self._wrap_key(key))

    def exists(self, key: str) -> bool:
        return self._parent.exists(self._wrap_key(key))

    def subscribe(self, key: str, callback: Callable) -> None:
        self._parent.subscribe(self._wrap_key(key), callback)

    def unsubscribe(self, key: str, callback: Callable = None) -> None:
        self._parent.unsubscribe(self._wrap_key(key), callback)

    def get_all_keys(self) -> List[str]:
        """获取当前命名空间下的所有键（去除前缀）"""
        all_keys = self._parent.get_all_keys()
        return [k[len(self._prefix):] for k in all_keys if k.startswith(self._prefix)]
