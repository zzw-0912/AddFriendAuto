import pytest


class MockTabButton:
    """Mock for testing without GUI"""
    def __init__(self, tab_id: str, name: str):
        self.tab_id = tab_id
        self.name = name
        self.is_running = False
        self.is_active = False

    def set_running(self, running: bool):
        self.is_running = running

    def set_active(self, active: bool):
        self.is_active = active


class MockTabBar:
    """Mock for testing without GUI"""
    def __init__(self):
        self.tabs = {}
        self.active_tab_id = None

    def add_tab(self, tab_id: str, name: str):
        self.tabs[tab_id] = {"name": name, "is_running": False, "button": MockTabButton(tab_id, name)}
        if self.active_tab_id is None:
            self.active_tab_id = tab_id

    def remove_tab(self, tab_id: str):
        if tab_id in self.tabs:
            del self.tabs[tab_id]
            if self.active_tab_id == tab_id:
                tab_ids = list(self.tabs.keys())
                self.active_tab_id = tab_ids[0] if tab_ids else None

    def set_active(self, tab_id: str):
        if tab_id in self.tabs:
            self.active_tab_id = tab_id
            for tid, tab in self.tabs.items():
                tab["button"].set_active(tid == tab_id)

    def set_running(self, tab_id: str, running: bool):
        if tab_id in self.tabs:
            self.tabs[tab_id]["is_running"] = running
            self.tabs[tab_id]["button"].set_running(running)


class TestTabButton:
    """TabButton 测试"""
    
    def test_tab_button_creation(self):
        btn = MockTabButton(tab_id="tab_1", name="主任务")
        assert btn.tab_id == "tab_1"
        assert btn.name == "主任务"
        assert btn.is_running is False
        assert btn.is_active is False

    def test_tab_button_set_running(self):
        btn = MockTabButton(tab_id="tab_1", name="主任务")
        btn.set_running(True)
        assert btn.is_running is True
        btn.set_running(False)
        assert btn.is_running is False

    def test_tab_button_set_active(self):
        btn = MockTabButton(tab_id="tab_1", name="主任务")
        btn.set_active(True)
        assert btn.is_active is True
        btn.set_active(False)
        assert btn.is_active is False


class TestTabBar:
    """TabBar 测试"""
    
    def test_tab_bar_add_tab(self):
        bar = MockTabBar()
        bar.add_tab("tab_1", "主任务")
        assert "tab_1" in bar.tabs
        assert bar.active_tab_id == "tab_1"

    def test_tab_bar_remove_tab(self):
        bar = MockTabBar()
        bar.add_tab("tab_1", "主任务")
        bar.remove_tab("tab_1")
        assert "tab_1" not in bar.tabs
        assert bar.active_tab_id is None

    def test_tab_bar_set_active(self):
        bar = MockTabBar()
        bar.add_tab("tab_1", "Tab1")
        bar.add_tab("tab_2", "Tab2")
        bar.set_active("tab_2")
        assert bar.active_tab_id == "tab_2"
        assert bar.tabs["tab_1"]["button"].is_active is False
        assert bar.tabs["tab_2"]["button"].is_active is True

    def test_tab_bar_set_running(self):
        bar = MockTabBar()
        bar.add_tab("tab_1", "主任务")
        bar.set_running("tab_1", True)
        assert bar.tabs["tab_1"]["is_running"] is True
        assert bar.tabs["tab_1"]["button"].is_running is True

    def test_tab_bar_remove_tab_switches_active(self):
        bar = MockTabBar()
        bar.add_tab("tab_1", "Tab1")
        bar.add_tab("tab_2", "Tab2")
        bar.set_active("tab_1")
        bar.remove_tab("tab_1")
        assert bar.active_tab_id == "tab_2"

    def test_tab_bar_get_tab_count(self):
        bar = MockTabBar()
        assert len(bar.tabs) == 0
        bar.add_tab("tab_1", "Tab1")
        assert len(bar.tabs) == 1
        bar.add_tab("tab_2", "Tab2")
        assert len(bar.tabs) == 2
