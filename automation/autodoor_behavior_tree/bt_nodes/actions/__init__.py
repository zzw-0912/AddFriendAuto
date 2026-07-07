from .keyboard import KeyPressNode
from .mouse import MouseClickNode, MouseMoveNode
from .scroll import MouseScrollNode
from .delay import DelayNode
from .variable import SetVariableNode
from .script import ScriptNode
from .code import CodeNode
from .alarm import AlarmNode
from .text_input import TextInputNode
from .start_tree import StartTreeNode
from .stop_tree import StopTreeNode
from .run_program import RunProgramNode
from .log_status import LogStatusNode
from .set_display import SetDisplayNode

from bt_core.registry import NodeRegistry

NodeRegistry.register("KeyPressNode", KeyPressNode)
NodeRegistry.register("MouseClickNode", MouseClickNode)
NodeRegistry.register("MouseMoveNode", MouseMoveNode)
NodeRegistry.register("MouseScrollNode", MouseScrollNode)
NodeRegistry.register("DelayNode", DelayNode)
NodeRegistry.register("SetVariableNode", SetVariableNode)
NodeRegistry.register("ScriptNode", ScriptNode)
NodeRegistry.register("CodeNode", CodeNode)
NodeRegistry.register("AlarmNode", AlarmNode)
NodeRegistry.register("TextInputNode", TextInputNode)
NodeRegistry.register("StartTreeNode", StartTreeNode)
NodeRegistry.register("StopTreeNode", StopTreeNode)
NodeRegistry.register("RunProgramNode", RunProgramNode)
NodeRegistry.register("LogStatusNode", LogStatusNode)
NodeRegistry.register("SetDisplayNode", SetDisplayNode)

__all__ = [
    "KeyPressNode",
    "MouseClickNode",
    "MouseMoveNode",
    "MouseScrollNode",
    "DelayNode",
    "SetVariableNode",
    "ScriptNode",
    "CodeNode",
    "AlarmNode",
    "TextInputNode",
    "StartTreeNode",
    "StopTreeNode",
    "RunProgramNode",
    "LogStatusNode",
    "SetDisplayNode",
]
