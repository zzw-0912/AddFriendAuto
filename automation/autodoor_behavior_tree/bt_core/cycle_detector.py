import os
from typing import List, Dict, Set, Optional


class CycleDetector:
    """循环引用检测器

    使用 DFS 检测行为树引用链中的循环依赖。
    在子树加载时执行检测，发现循环直接拒绝。
    """

    def check(self, subtree_stack: List[str], new_path: str) -> bool:
        """检查添加新路径是否会形成循环

        Args:
            subtree_stack: 当前引用链（已加载的子树路径列表）
            new_path: 即将加载的子树路径

        Returns:
            True 表示无循环，可以加载；False 表示有循环，拒绝加载
        """
        normalized_new = os.path.normpath(os.path.abspath(new_path))

        for existing_path in subtree_stack:
            normalized_existing = os.path.normpath(os.path.abspath(existing_path))
            if normalized_existing == normalized_new:
                return False

        return True

    def check_with_context(self, context, new_path: str) -> bool:
        """使用 ExecutionContext 检查循环

        Args:
            context: 执行上下文（包含 _subtree_stack）
            new_path: 即将加载的子树路径

        Returns:
            True 表示无循环；False 表示有循环
        """
        subtree_stack = getattr(context, '_subtree_stack', [])
        return self.check(subtree_stack, new_path)

    def build_reference_graph(self, root_path: str, project_root: str = None) -> Dict[str, List[str]]:
        """构建引用关系图（用于可视化调试）

        Args:
            root_path: 根行为树路径
            project_root: 项目根目录

        Returns:
            {文件路径: [引用的子树路径列表]}
        """
        graph = {}
        visited: Set[str] = set()

        def traverse(path: str):
            normalized = os.path.normpath(os.path.abspath(path))
            if normalized in visited:
                return
            visited.add(normalized)

            try:
                from .serializer import Serializer
                node, _, _ = Serializer.load_from_file(path)
                subtree_refs = self._extract_subtree_refs(node)

                resolved_refs = []
                for ref in subtree_refs:
                    if not os.path.isabs(ref):
                        if project_root:
                            ref = os.path.join(project_root, ref)
                    resolved_refs.append(os.path.normpath(os.path.abspath(ref)))

                graph[normalized] = resolved_refs

                for ref in resolved_refs:
                    if os.path.exists(ref):
                        traverse(ref)

            except Exception:
                pass

        traverse(root_path)
        return graph

    def _extract_subtree_refs(self, node) -> List[str]:
        """从节点树中提取所有子树引用路径"""
        refs = []

        subtree_path = node.config.get("subtree_path", "") if hasattr(node, 'config') else ""
        if subtree_path:
            refs.append(subtree_path)

        for child in getattr(node, 'children', []):
            refs.extend(self._extract_subtree_refs(child))

        return refs

    def detect_cycle_in_graph(self, graph: Dict[str, List[str]]) -> Optional[List[str]]:
        """检测图中是否存在循环

        Args:
            graph: 引用关系图

        Returns:
            如果存在循环，返回循环路径；否则返回 None
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]

            path.pop()
            rec_stack.remove(node)
            return None

        for node in graph:
            if node not in visited:
                result = dfs(node)
                if result:
                    return result

        return None
