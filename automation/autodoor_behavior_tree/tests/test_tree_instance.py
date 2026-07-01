import pytest
from unittest.mock import MagicMock


class TestTreeInstanceGUIFields:
    """TreeInstance GUI 字段测试"""
    
    def test_tree_instance_gui_fields(self):
        from bt_core.tree_instance import TreeInstance
        from bt_core.engine import BehaviorTreeEngine
        from bt_core.context import ExecutionContext
        from bt_core.blackboard import Blackboard
        
        mock_canvas = MagicMock()
        mock_command_manager = MagicMock()
        
        instance = TreeInstance(
            name="测试树",
            engine=BehaviorTreeEngine(None),
            context=ExecutionContext(),
            blackboard=Blackboard(),
            tab_id="tab_1",
            canvas=mock_canvas,
            file_path="/path/to/tree.json",
            project_root="/path/to/project",
            modified=True,
            command_manager=mock_command_manager,
            selected_node_id="node_1"
        )
        
        assert instance.tab_id == "tab_1"
        assert instance.canvas == mock_canvas
        assert instance.file_path == "/path/to/tree.json"
        assert instance.project_root == "/path/to/project"
        assert instance.modified is True
        assert instance.command_manager == mock_command_manager
        assert instance.selected_node_id == "node_1"
    
    def test_tree_instance_is_running(self):
        from bt_core.tree_instance import TreeInstance
        
        instance = TreeInstance(
            name="测试树",
            engine=MagicMock(),
            context=MagicMock(),
            blackboard=MagicMock()
        )
        
        assert instance.is_running is False
        assert instance.status == "idle"
        
        instance.set_running(True)
        assert instance.is_running is True
        assert instance.status == "running"
        
        instance.set_running(False)
        assert instance.is_running is False
        assert instance.status == "stopped"
    
    def test_tree_instance_to_dict_includes_gui_fields(self):
        from bt_core.tree_instance import TreeInstance
        
        instance = TreeInstance(
            name="测试树",
            engine=MagicMock(),
            context=MagicMock(),
            blackboard=MagicMock(),
            tab_id="tab_1",
            file_path="/path/to/tree.json",
            project_root="/path/to/project",
            modified=True,
            selected_node_id="node_1"
        )
        
        data = instance.to_dict()
        
        assert data["name"] == "测试树"
        assert data["tab_id"] == "tab_1"
        assert data["file_path"] == "/path/to/tree.json"
        assert data["project_root"] == "/path/to/project"
        assert data["modified"] is True
        assert data["selected_node_id"] == "node_1"
    
    def test_tree_instance_default_values(self):
        from bt_core.tree_instance import TreeInstance
        
        instance = TreeInstance(
            name="测试树",
            engine=MagicMock(),
            context=MagicMock(),
            blackboard=MagicMock()
        )
        
        assert instance.tab_id is None
        assert instance.canvas is None
        assert instance.file_path is None
        assert instance.project_root is None
        assert instance.modified is False
        assert instance.command_manager is None
        assert instance.selected_node_id is None
