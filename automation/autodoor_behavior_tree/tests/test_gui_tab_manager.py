import pytest
from unittest.mock import MagicMock


class TestGuiTabManager:
    """GuiTabManager 测试"""
    
    def test_gui_tab_manager_init(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        
        manager = GuiTabManager()
        assert manager.active_tab_id is None
        assert manager.on_tab_switched is None
        assert manager.on_tab_status_changed is None
        assert manager.get_tab_count() == 0
    
    def test_gui_tab_manager_add_tab(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        mock_canvas = MagicMock()
        instance = TreeInstance(
            name="主任务",
            engine=MagicMock(),
            context=MagicMock(),
            blackboard=MagicMock(),
            tab_id="tab_1",
            canvas=mock_canvas
        )
        
        manager.add_tab("tab_1", instance)
        assert manager.active_tab_id == "tab_1"
        assert manager.get_tab("tab_1") == instance
        assert manager.get_tab_count() == 1
    
    def test_gui_tab_manager_switch_tab(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        instance1 = TreeInstance(
            name="Tab1", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_1"
        )
        instance2 = TreeInstance(
            name="Tab2", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_2"
        )
        
        manager.add_tab("tab_1", instance1)
        manager.add_tab("tab_2", instance2)
        
        manager.switch_tab("tab_2")
        assert manager.active_tab_id == "tab_2"
        
        active = manager.get_active_tab()
        assert active == instance2
    
    def test_gui_tab_manager_switch_nonexistent(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        
        manager = GuiTabManager()
        with pytest.raises(ValueError):
            manager.switch_tab("nonexistent")
    
    def test_gui_tab_manager_remove_tab(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        instance = TreeInstance(
            name="Tab1", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_1"
        )
        
        manager.add_tab("tab_1", instance)
        result = manager.remove_tab("tab_1")
        
        assert result is True
        assert manager.active_tab_id is None
        assert manager.get_tab("tab_1") is None
        assert manager.get_tab_count() == 0
    
    def test_gui_tab_manager_remove_tab_switches_active(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        instance1 = TreeInstance(
            name="Tab1", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_1"
        )
        instance2 = TreeInstance(
            name="Tab2", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_2"
        )
        
        manager.add_tab("tab_1", instance1)
        manager.add_tab("tab_2", instance2)
        manager.switch_tab("tab_1")
        
        manager.remove_tab("tab_1")
        
        assert manager.active_tab_id == "tab_2"
    
    def test_gui_tab_manager_callbacks(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        switched_called = []
        status_changed_called = []
        added_called = []
        removed_called = []
        
        def on_switched(tab_id, instance):
            switched_called.append((tab_id, instance.name))
        
        def on_status_changed(tab_id, running):
            status_changed_called.append((tab_id, running))
        
        def on_added(tab_id, instance):
            added_called.append((tab_id, instance.name))
        
        def on_removed(tab_id):
            removed_called.append(tab_id)
        
        manager.on_tab_switched = on_switched
        manager.on_tab_status_changed = on_status_changed
        manager.on_tab_added = on_added
        manager.on_tab_removed = on_removed
        
        instance1 = TreeInstance(
            name="Tab1", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_1"
        )
        instance2 = TreeInstance(
            name="Tab2", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_2"
        )
        
        manager.add_tab("tab_1", instance1)
        assert len(added_called) == 1
        assert added_called[0] == ("tab_1", "Tab1")
        
        manager.add_tab("tab_2", instance2)
        assert len(added_called) == 2
        
        manager.switch_tab("tab_2")
        assert len(switched_called) == 1
        assert switched_called[0] == ("tab_2", "Tab2")
        
        manager.update_tab_status("tab_2", True)
        assert len(status_changed_called) == 1
        assert status_changed_called[0] == ("tab_2", True)
        
        manager.remove_tab("tab_2")
        assert len(removed_called) == 1
        assert removed_called[0] == "tab_2"
    
    def test_gui_tab_manager_get_all_status(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        instance1 = TreeInstance(
            name="Tab1", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_1", modified=True
        )
        instance2 = TreeInstance(
            name="Tab2", engine=MagicMock(), context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_2", modified=False
        )
        
        manager.add_tab("tab_1", instance1)
        manager.add_tab("tab_2", instance2)
        
        status = manager.get_all_status()
        
        assert len(status) == 2
        assert any(s["tab_id"] == "tab_1" and s["name"] == "Tab1" and s["modified"] is True for s in status)
        assert any(s["tab_id"] == "tab_2" and s["name"] == "Tab2" and s["modified"] is False for s in status)
    
    def test_gui_tab_manager_start_stop_tab(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        mock_engine = MagicMock()
        instance = TreeInstance(
            name="Tab1", engine=mock_engine, context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_1"
        )
        
        manager.add_tab("tab_1", instance)
        
        result = manager.start_tab("tab_1")
        assert result is True
        mock_engine.start.assert_called_once()
        assert instance.is_running is True
        
        result = manager.stop_tab("tab_1")
        assert result is True
        mock_engine.stop.assert_called_once()
        assert instance.is_running is False
    
    def test_gui_tab_manager_start_all_stop_all(self):
        from bt_gui.bt_editor.gui_tab_manager import GuiTabManager
        from bt_core.tree_instance import TreeInstance
        
        manager = GuiTabManager()
        
        mock_engine1 = MagicMock()
        mock_engine2 = MagicMock()
        
        instance1 = TreeInstance(
            name="Tab1", engine=mock_engine1, context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_1"
        )
        instance2 = TreeInstance(
            name="Tab2", engine=mock_engine2, context=MagicMock(), 
            blackboard=MagicMock(), tab_id="tab_2"
        )
        
        manager.add_tab("tab_1", instance1)
        manager.add_tab("tab_2", instance2)
        
        count = manager.start_all()
        assert count == 2
        mock_engine1.start.assert_called_once()
        mock_engine2.start.assert_called_once()
        
        count = manager.stop_all()
        assert count == 2
        mock_engine1.stop.assert_called_once()
        mock_engine2.stop.assert_called_once()
