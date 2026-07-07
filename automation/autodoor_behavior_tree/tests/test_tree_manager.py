import pytest
from bt_core.tree_manager import MultiTreeManager
from bt_core.tree_instance import TreeInstance
from bt_core.nodes import SequenceNode
from bt_core.config import NodeConfig
from bt_core.engine import BehaviorTreeEngine
from bt_core.context import ExecutionContext
from bt_core.blackboard import Blackboard


class TestTreeInstance:
    def test_initialization(self):
        engine = BehaviorTreeEngine()
        context = ExecutionContext()
        blackboard = Blackboard()
        
        instance = TreeInstance(
            name="test_tree",
            engine=engine,
            context=context,
            blackboard=blackboard
        )
        
        assert instance.name == "test_tree"
        assert instance.engine is engine
        assert instance.context is context
        assert instance.blackboard is blackboard
        assert instance.status == "idle"
    
    def test_status_transitions(self):
        instance = TreeInstance(
            name="test",
            engine=BehaviorTreeEngine(),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        
        assert instance.status == "idle"
        instance.status = "running"
        assert instance.status == "running"
        instance.status = "paused"
        assert instance.status == "paused"
    
    def test_to_dict(self):
        instance = TreeInstance(
            name="test",
            engine=BehaviorTreeEngine(),
            context=ExecutionContext(),
            blackboard=Blackboard()
        )
        
        data = instance.to_dict()
        assert data["name"] == "test"
        assert data["status"] == "idle"


class TestMultiTreeManager:
    def test_initialization(self):
        manager = MultiTreeManager()
        assert manager._trees == {}
        assert manager._shared_blackboard is None
    
    def test_initialization_with_shared_blackboard(self):
        manager = MultiTreeManager(shared_blackboard=True)
        assert manager._shared_blackboard is not None
    
    def test_add_tree(self):
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        instance = manager.add_tree("test_tree", root)
        
        assert instance is not None
        assert instance.name == "test_tree"
        assert "test_tree" in manager._trees
    
    def test_add_tree_duplicate_name(self):
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        manager.add_tree("test_tree", root)
        
        with pytest.raises(ValueError):
            manager.add_tree("test_tree", root)
    
    def test_remove_tree(self):
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        manager.add_tree("test_tree", root)
        result = manager.remove_tree("test_tree")
        
        assert result == True
        assert "test_tree" not in manager._trees
    
    def test_remove_nonexistent_tree(self):
        manager = MultiTreeManager()
        result = manager.remove_tree("nonexistent")
        assert result == False
    
    def test_get_tree_status(self):
        manager = MultiTreeManager()
        root = SequenceNode(config=NodeConfig(name="test"))
        
        manager.add_tree("test_tree", root)
        status = manager.get_tree_status("test_tree")
        
        assert status is not None
        assert status["name"] == "test_tree"
        assert status["status"] == "idle"
    
    def test_get_all_status(self):
        manager = MultiTreeManager()
        root1 = SequenceNode(config=NodeConfig(name="test1"))
        root2 = SequenceNode(config=NodeConfig(name="test2"))
        
        manager.add_tree("tree1", root1)
        manager.add_tree("tree2", root2)
        
        all_status = manager.get_all_status()
        
        assert len(all_status) == 2
        assert "tree1" in all_status
        assert "tree2" in all_status
    
    def test_shared_blackboard_communication(self):
        manager = MultiTreeManager(shared_blackboard=True)
        
        root1 = SequenceNode(config=NodeConfig(name="tree1"))
        root2 = SequenceNode(config=NodeConfig(name="tree2"))
        
        instance1 = manager.add_tree("tree1", root1)
        instance2 = manager.add_tree("tree2", root2)
        
        instance1.blackboard.set("shared_var", "value")
        
        assert instance2.blackboard.get("shared_var") == "value"
    
    def test_get_nonexistent_tree_status(self):
        manager = MultiTreeManager()
        status = manager.get_tree_status("nonexistent")
        assert status is None
