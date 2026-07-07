from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any, Optional
import time
from bt_utils.log_manager import LogManager


class AlarmNode(ActionNode):
    NODE_TYPE = "AlarmNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        
        from bt_utils.resource_manager import ResourceManager
        from config.settings_manager import SettingsManager
        
        default_sound = ResourceManager().get_alarm_sound_path()
        default_volume = SettingsManager().get("alarm_volume", 70)
        
        self.sound_path = self.config.get("sound_path", default_sound)
        self.volume = self.config.get_int("volume", default_volume)
        self.wait_complete = self.config.get_bool("wait_complete", True)
        
        self._sound_started = False
        self._sound_start_time: Optional[float] = None
        self._sound_duration: Optional[float] = None
        self._abort_flag = False
        
        if "sound_path" not in self.config.extra:
            self.config.set("sound_path", default_sound)
        
        if "volume" not in self.config.extra:
            self.config.set("volume", default_volume)

    def _execute_action(self, context) -> NodeStatus:
        try:
            if self._abort_flag or not context.check_running():
                self._stop_sound()
                LogManager.instance().log_aborted(
                    node_type="报警节点",
                    node_name=self.name
                )
                return NodeStatus.ABORTED

            if not self._sound_started:
                sound_path = self.config.get("sound_path", "")
                resolved_sound_path = context.resolve_path(sound_path)
                
                if not resolved_sound_path:
                    LogManager.instance().log_failure(
                        node_type="报警节点",
                        node_name=self.name,
                        reason="无法解析音频文件路径"
                    )
                    return NodeStatus.FAILURE
                
                from bt_utils.alarm import AlarmPlayer
                import pygame
                
                player = AlarmPlayer()
                player._init_pygame()
                
                if not player._pygame_initialized:
                    LogManager.instance().log_failure(
                        node_type="报警节点",
                        node_name=self.name,
                        reason="无法初始化音频系统"
                    )
                    return NodeStatus.FAILURE
                
                try:
                    sound = pygame.mixer.Sound(resolved_sound_path)
                    sound.set_volume(self.config.get_int("volume", 70) / 100)
                    sound.play()
                    
                    self._sound_started = True
                    self._sound_start_time = time.time()
                    self._sound_duration = sound.get_length()
                    
                    LogManager.instance().log_info(
                        node_type="报警节点",
                        node_name=self.name,
                        message=f"开始播放音频"
                    )
                except Exception as e:
                    from bt_utils.exception_handler import log_exception
                    log_exception(e, f"AlarmNode '{self.name}' 音频播放失败")
                    LogManager.instance().log_failure(
                        node_type="报警节点",
                        node_name=self.name,
                        reason="音频播放失败，详情见终端日志"
                    )
                    return NodeStatus.FAILURE
            
            if self.config.get_bool("wait_complete", True):
                if self._sound_start_time is None or self._sound_duration is None:
                    self._stop_sound()
                    return NodeStatus.FAILURE
                
                elapsed = time.time() - self._sound_start_time
                
                if elapsed < self._sound_duration:
                    return NodeStatus.RUNNING
                
                # wait_complete = True 时，播放完成后停止音频
                self._stop_sound()
            else:
                # wait_complete = False 时，只重置状态标志，不停止音频
                self._sound_started = False
                self._sound_start_time = None
                self._sound_duration = None
                self._abort_flag = False
            
            LogManager.instance().log_success(
                node_type="报警节点",
                node_name=self.name
            )
            
            return NodeStatus.SUCCESS

        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"AlarmNode '{self.name}'")
            LogManager.instance().log_failure(
                node_type="报警节点",
                node_name=self.name,
                reason="执行异常，详情见终端日志"
            )
            return NodeStatus.FAILURE

    def _stop_sound(self) -> None:
        """停止音频播放并重置状态"""
        try:
            from bt_utils.alarm import AlarmPlayer
            AlarmPlayer().stop()
        except Exception:
            pass
        
        self._sound_started = False
        self._sound_start_time = None
        self._sound_duration = None
        self._abort_flag = False

    def abort(self, context) -> None:
        """中止节点执行"""
        self._abort_flag = True
        self._stop_sound()
        super().abort(context)

    def reset(self, reset_counters: bool = True) -> None:
        """重置节点状态"""
        self._stop_sound()
        super().reset(reset_counters=reset_counters)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlarmNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node
