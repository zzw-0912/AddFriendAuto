import pytest
import os
import json
import tempfile
from bt_core.serializer import Serializer
from bt_core.nodes import SubtreeNode, SequenceNode
from bt_core.config import NodeConfig
from bt_core.registry import register_all_nodes


class TestSerializerSubtree:
    @classmethod
    def setup_class(cls):
        register_all_nodes()
    
    def test_serialize_subtree_node(self):
        config = NodeConfig(name="登录流程")
        config.set("subtree_path", "subtrees/login.json")
        config.set("blackboard_mode", "namespaced")
        config.set("namespace", "login")
        
        subtree = SubtreeNode(config=config)
        
        data = Serializer.serialize(subtree)
        
        assert "nodes" in data
        assert data["version"] == "2.0"
        
        node_data = data["nodes"][subtree.node_id]
        assert node_data["type"] == "SubtreeNode"
        assert node_data["config"]["subtree_path"] == "subtrees/login.json"
        assert node_data["config"]["blackboard_mode"] == "namespaced"
    
    def test_deserialize_subtree_node(self):
        data = {
            "version": "2.0",
            "format_type": "behavior_tree_standalone",
            "root_node": "sub_1",
            "nodes": {
                "sub_1": {
                    "id": "sub_1",
                    "type": "SubtreeNode",
                    "name": "登录流程",
                    "config": {
                        "subtree_path": "subtrees/login.json",
                        "blackboard_mode": "inherit"
                    }
                }
            },
            "connections": []
        }
        
        root, canvas_state, editor_state = Serializer.deserialize(data)
        
        assert root is not None
        assert root.NODE_TYPE == "SubtreeNode"
        assert root.subtree_path == "subtrees/login.json"
    
    def test_collect_subtree_refs(self):
        config1 = NodeConfig(name="登录")
        config1.set("subtree_path", "login.json")
        
        config2 = NodeConfig(name="登出")
        config2.set("subtree_path", "logout.json")
        
        subtree1 = SubtreeNode(config=config1)
        subtree2 = SubtreeNode(config=config2)
        
        seq = SequenceNode(config=NodeConfig(name="主流程"))
        seq.add_child(subtree1)
        seq.add_child(subtree2)
        
        refs = {}
        Serializer._collect_subtree_refs(seq, refs, "/project")
        
        assert subtree1.node_id in refs
        assert subtree2.node_id in refs
        assert refs[subtree1.node_id]["path"] == "login.json"
        assert refs[subtree2.node_id]["path"] == "logout.json"
    
    def test_serialize_with_subtrees(self):
        config = NodeConfig(name="登录")
        config.set("subtree_path", "login.json")
        
        subtree = SubtreeNode(config=config)
        
        data = Serializer.serialize_with_subtrees(subtree, project_root="/project")
        
        assert data["version"] == "2.1"
        assert data["format_type"] == "behavior_tree_with_subtrees"
        assert "subtree_references" in data
    
    def test_count_nodes(self):
        seq = SequenceNode(config=NodeConfig(name="test"))
        from bt_core.nodes import SelectorNode
        sel = SelectorNode(config=NodeConfig(name="child1"))
        seq.add_child(sel)
        
        count = Serializer._count_nodes(seq)
        assert count == 2
