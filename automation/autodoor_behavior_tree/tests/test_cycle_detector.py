import pytest
import os
from bt_core.cycle_detector import CycleDetector


class TestCycleDetector:
    def test_check_no_cycle(self):
        detector = CycleDetector()
        context_stack = ["main.json", "subtree_a.json"]
        
        result = detector.check(context_stack, "subtree_b.json")
        assert result == True
    
    def test_check_detects_direct_cycle(self):
        detector = CycleDetector()
        context_stack = ["main.json", "subtree_a.json"]
        
        result = detector.check(context_stack, "main.json")
        assert result == False
    
    def test_check_detects_indirect_cycle(self):
        detector = CycleDetector()
        context_stack = ["a.json", "b.json", "c.json"]
        
        result = detector.check(context_stack, "a.json")
        assert result == False
    
    def test_check_with_normalized_paths(self):
        detector = CycleDetector()
        context_stack = [os.path.join(".", "subtrees", "login.json")]
        
        result = detector.check(context_stack, os.path.join("subtrees", "login.json"))
        assert result == False
    
    def test_check_empty_stack(self):
        detector = CycleDetector()
        
        result = detector.check([], "any_file.json")
        assert result == True
    
    def test_extract_subtree_refs_no_subtree(self):
        from bt_core.nodes import SequenceNode
        from bt_core.config import NodeConfig
        
        detector = CycleDetector()
        seq = SequenceNode(config=NodeConfig(name="test"))
        refs = detector._extract_subtree_refs(seq)
        assert refs == []
    
    def test_detect_cycle_in_graph_no_cycle(self):
        detector = CycleDetector()
        graph = {
            "a.json": ["b.json"],
            "b.json": ["c.json"],
            "c.json": []
        }
        
        result = detector.detect_cycle_in_graph(graph)
        assert result is None
    
    def test_detect_cycle_in_graph_with_cycle(self):
        detector = CycleDetector()
        graph = {
            "a.json": ["b.json"],
            "b.json": ["c.json"],
            "c.json": ["a.json"]
        }
        
        result = detector.detect_cycle_in_graph(graph)
        assert result is not None
        assert len(result) > 1
