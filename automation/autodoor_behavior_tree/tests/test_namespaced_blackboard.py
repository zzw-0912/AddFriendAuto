import pytest
from bt_core.blackboard import Blackboard, NamespacedBlackboard


class TestNamespacedBlackboard:
    def test_wrap_key_adds_prefix(self):
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "login")
        
        assert ns_bb._wrap_key("username") == "login.username"
        assert ns_bb._wrap_key("login.username") == "login.username"
    
    def test_set_writes_to_parent_with_prefix(self):
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "login")
        
        ns_bb.set("username", "admin")
        
        assert parent.get("login.username") == "admin"
        assert ns_bb.get("username") == "admin"
    
    def test_get_reads_from_parent_with_prefix(self):
        parent = Blackboard()
        parent.set("login.username", "admin")
        
        ns_bb = NamespacedBlackboard(parent, "login")
        
        assert ns_bb.get("username") == "admin"
    
    def test_isolation_between_namespaces(self):
        parent = Blackboard()
        
        login_bb = NamespacedBlackboard(parent, "login")
        logout_bb = NamespacedBlackboard(parent, "logout")
        
        login_bb.set("status", "success")
        logout_bb.set("status", "pending")
        
        assert login_bb.get("status") == "success"
        assert logout_bb.get("status") == "pending"
        assert parent.get("login.status") == "success"
        assert parent.get("logout.status") == "pending"
    
    def test_get_all_keys_filters_by_namespace(self):
        parent = Blackboard()
        parent.set("login.username", "admin")
        parent.set("login.password", "123456")
        parent.set("logout.status", "done")
        
        ns_bb = NamespacedBlackboard(parent, "login")
        
        keys = ns_bb.get_all_keys()
        assert "username" in keys
        assert "password" in keys
        assert "status" not in keys
    
    def test_increment(self):
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "counter")
        
        ns_bb.set("value", 0)
        ns_bb.increment("value", 5)
        
        assert ns_bb.get("value") == 5
        assert parent.get("counter.value") == 5
    
    def test_exists(self):
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "test")
        
        assert ns_bb.exists("key") == False
        ns_bb.set("key", "value")
        assert ns_bb.exists("key") == True
    
    def test_delete(self):
        parent = Blackboard()
        ns_bb = NamespacedBlackboard(parent, "test")
        
        ns_bb.set("key", "value")
        assert ns_bb.exists("key") == True
        
        ns_bb.delete("key")
        assert ns_bb.exists("key") == False
