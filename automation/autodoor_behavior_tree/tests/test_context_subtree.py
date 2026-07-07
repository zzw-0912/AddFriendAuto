import pytest
from bt_core.context import ExecutionContext


class TestExecutionContextSubtree:
    def test_subtree_stack_initialization(self):
        ctx = ExecutionContext()
        assert hasattr(ctx, '_subtree_stack')
        assert ctx._subtree_stack == []
    
    def test_push_subtree(self):
        ctx = ExecutionContext()
        ctx.push_subtree("subtrees/login.json")
        assert ctx.get_subtree_depth() == 1
        assert ctx.is_in_subtree("subtrees/login.json")
    
    def test_pop_subtree(self):
        ctx = ExecutionContext()
        ctx.push_subtree("subtrees/login.json")
        ctx.push_subtree("subtrees/action.json")
        assert ctx.get_subtree_depth() == 2
        
        popped = ctx.pop_subtree()
        assert popped == "subtrees/action.json"
        assert ctx.get_subtree_depth() == 1
    
    def test_can_enter_subtree(self):
        ctx = ExecutionContext()
        for i in range(ExecutionContext.MAX_SUBTREE_DEPTH):
            assert ctx.can_enter_subtree() == True
            ctx.push_subtree(f"subtree_{i}.json")
        
        assert ctx.can_enter_subtree() == False
    
    def test_parent_context_reference(self):
        parent = ExecutionContext()
        child = ExecutionContext()
        child._parent_context = parent
        
        assert child._parent_context is parent
    
    def test_is_in_subtree_normalized(self):
        ctx = ExecutionContext()
        ctx.push_subtree("subtrees/login.json")
        
        assert ctx.is_in_subtree("subtrees/login.json") == True
        assert ctx.is_in_subtree("other.json") == False
    
    def test_pop_empty_stack(self):
        ctx = ExecutionContext()
        result = ctx.pop_subtree()
        assert result is None
