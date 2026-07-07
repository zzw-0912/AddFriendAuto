from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any
from bt_utils.log_manager import LogManager


class StartTreeNode(ActionNode):
    """启动行为树节点

    启动其他已加载到程序中的行为树。
    成功启动后立即返回 SUCCESS。
    """
    NODE_TYPE = "StartTreeNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)

        self.target_tree = self.config.get("target_tree", "")
        self.sound_path = self.config.get("sound_path", "")
        self.volume = self.config.get_int("volume", 70)

        self._abort_flag = False

    def _execute_action(self, context) -> NodeStatus:
        if self._abort_flag or not context.check_running():
            LogManager.instance().log_aborted(
                node_type="启动树",
                node_name=self.name
            )
            return NodeStatus.ABORTED

        # 获取 Tab 管理器
        tab_manager = context.get_tab_manager()
        if not tab_manager:
            LogManager.instance().log_failure(
                node_type="启动树",
                node_name=self.name,
                reason="无法访问行为树管理器"
            )
            return NodeStatus.SUCCESS

        # 查找目标 Tab
        target_name = self.config.get("target_tree", "")
        target_tab_id = self._find_tab_by_name(tab_manager, target_name)

        if not target_tab_id:
            LogManager.instance().log_failure(
                node_type="启动树",
                node_name=self.name,
                reason=f"未找到行为树 '{target_name}'"
            )
            return NodeStatus.SUCCESS

        # 检查目标是否已在运行
        target_instance = tab_manager.get_tab(target_tab_id)
        if target_instance and target_instance.is_running:
            LogManager.instance().log_info(
                node_type="启动树",
                node_name=self.name,
                message=f"行为树 '{target_name}' 已在运行中"
            )
            return NodeStatus.SUCCESS

        # 播放启动音效
        self._play_sound(context)

        # 启动目标行为树（跳过默认音效，由节点自身播放）
        tab_manager.start_tab(target_tab_id, skip_sound=True)

        LogManager.instance().log_success(
            node_type="启动树",
            node_name=self.name
        )
        return NodeStatus.SUCCESS

    def _find_tab_by_name(self, tab_manager, name: str) -> str:
        """根据名称查找 Tab ID"""
        for tab_id, instance in tab_manager._trees.items():
            if instance.name == name:
                return tab_id
        return None

    def _play_sound(self, context):
        """播放启动音效"""
        try:
            from bt_utils.alarm import AlarmPlayer

            sound_path = self.config.get("sound_path", "")
            if sound_path:
                resolved = context.resolve_path(sound_path)
            else:
                from bt_utils.resource_manager import get_resource_manager
                resolved = get_resource_manager().get_start_sound_path()

            if resolved:
                player = AlarmPlayer()
                volume = self.config.get_int("volume", 70)
                player.play(resolved, volume, wait_complete=False)
        except Exception:
            pass

    def abort(self, context) -> None:
        self._abort_flag = True
        super().abort(context)

    def reset(self, reset_counters: bool = True) -> None:
        self._abort_flag = False
        super().reset(reset_counters)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StartTreeNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        return cls(node_id=data.get("id"), config=config)
