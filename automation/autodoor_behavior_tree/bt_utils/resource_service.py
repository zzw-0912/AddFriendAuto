import os
import shutil
from typing import Dict, List, Set, Any, Optional
from datetime import datetime
from bt_utils.log_manager import LogManager


class ResourceService:
    RESOURCE_KEYS = [
        'template_path',
        'script_path', 
        'code_path',
        'sound_path',
        'file_path',
        'subtree_path',
    ]
    
    RESOURCE_TYPE_MAP = {
        'template_path': 'image',
        'script_path': 'script',
        'code_path': 'code',
        'sound_path': 'audio',
        'file_path': 'data',
        'subtree_path': 'subtree',
    }
    
    TYPE_DIR_MAP = {
        'image': 'images/templates',
        'script': 'scripts/script',
        'code': 'scripts/code',
        'audio': 'audio/alarms',
        'data': 'data/config',
        'subtree': 'subtrees',
        'other': 'data/other',
    }
    
    CACHE_DIR = 'cache'
    
    RESOURCE_EXTENSIONS = {
        'image': ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'],
        'script': ['.py', '.bat', '.cmd', '.sh', '.ps1'],
        'audio': ['.mp3', '.wav', '.ogg', '.flac'],
        'data': ['.json', '.yaml', '.yml', '.xml', '.txt', '.csv'],
    }
    
    @classmethod
    def is_path_in_project(cls, abs_path: str, abs_project_root: str) -> bool:
        """判断绝对路径是否在项目根目录内（确保目录边界，兼容 Windows 大小写）
        
        Args:
            abs_path: 文件的绝对路径
            abs_project_root: 项目根目录的绝对路径
            
        Returns:
            是否在项目根目录内
        """
        norm_root = os.path.normpath(os.path.normcase(abs_project_root))
        norm_path = os.path.normpath(os.path.normcase(abs_path))
        return norm_path.startswith(norm_root + os.sep) or norm_path == norm_root
    
    @classmethod
    def collect_external_resources(cls, tree_data: Dict[str, Any], project_root: str) -> List[Dict[str, str]]:
        external_resources = []
        
        if not project_root or not os.path.exists(project_root):
            return external_resources
        
        abs_project_root = os.path.abspath(project_root)
        nodes = tree_data.get("nodes", {})
        
        if isinstance(nodes, dict):
            for node_id, node in nodes.items():
                config = node.get("config", {})
                
                for key in cls.RESOURCE_KEYS:
                    if key in config:
                        path_value = config[key]
                        
                        if not path_value or not isinstance(path_value, str):
                            continue
                        
                        if key == 'subtree_path':
                            continue
                        
                        if path_value.startswith("./"):
                            abs_path = os.path.normpath(os.path.join(project_root, path_value[2:]))
                        else:
                            abs_path = os.path.abspath(path_value)
                        
                        if not os.path.exists(abs_path):
                            continue
                        
                        if not cls.is_path_in_project(abs_path, abs_project_root):
                            resource_type = cls.RESOURCE_TYPE_MAP.get(key, 'other')
                            
                            external_resources.append({
                                'node_id': node_id,
                                'key': key,
                                'original_path': path_value,
                                'absolute_path': abs_path,
                                'resource_type': resource_type,
                            })
        
        return external_resources
    
    @classmethod
    def import_resources_to_project(cls, 
                                     external_resources: List[Dict[str, str]], 
                                     project_root: str) -> Dict[str, str]:
        path_mapping = {}
        
        if not external_resources:
            return path_mapping
        
        for resource in external_resources:
            original_path = resource['original_path']
            absolute_path = resource['absolute_path']
            resource_type = resource['resource_type']
            
            relative_path = cls._import_single_resource(
                absolute_path, 
                project_root, 
                resource_type
            )
            
            if relative_path:
                path_mapping[original_path] = relative_path
                path_mapping[absolute_path] = relative_path
        
        return path_mapping
    
    @classmethod
    def _import_single_resource(cls, 
                                source_path: str, 
                                project_root: str, 
                                resource_type: str) -> Optional[str]:
        if not os.path.exists(source_path):
            return None
        
        target_dir = cls.TYPE_DIR_MAP.get(resource_type, 'data/other')
        filename = os.path.basename(source_path)
        filename = cls._handle_name_conflict(project_root, target_dir, filename)
        
        target_path = os.path.join(project_root, target_dir, filename)
        
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        try:
            shutil.copy2(source_path, target_path)
            return f"./{target_dir}/{filename}".replace(os.sep, '/')
        except Exception as e:
            LogManager.debug_print(f"[ERROR] 导入资源失败 {source_path}: {e}")
            return None
    
    @classmethod
    def _handle_name_conflict(cls, project_root: str, target_dir: str, filename: str) -> str:
        target_path = os.path.join(project_root, target_dir, filename)
        
        if not os.path.exists(target_path):
            return filename
        
        name, ext = os.path.splitext(filename)
        counter = 2
        new_filename = filename
        
        while os.path.exists(target_path):
            new_filename = f"{name}_{counter}{ext}"
            target_path = os.path.join(project_root, target_dir, new_filename)
            counter += 1
        
        return new_filename
    
    @classmethod
    def update_tree_paths(cls, 
                          tree_data: Dict[str, Any], 
                          path_mapping: Dict[str, str]) -> Dict[str, Any]:
        if not path_mapping:
            return tree_data
        
        nodes = tree_data.get("nodes", {})
        
        if isinstance(nodes, dict):
            for node_id, node in nodes.items():
                config = node.get("config", {})
                
                for key in cls.RESOURCE_KEYS:
                    if key in config:
                        original_value = config[key]
                        
                        if original_value in path_mapping:
                            config[key] = path_mapping[original_value]
        
        return tree_data
    
    @classmethod
    def get_all_referenced_files(cls, 
                                  tree_data: Dict[str, Any], 
                                  project_root: str) -> Set[str]:
        referenced_files = set()
        
        if not project_root:
            return referenced_files
        
        nodes = tree_data.get("nodes", {})
        
        if isinstance(nodes, dict):
            for node_id, node in nodes.items():
                config = node.get("config", {})
                
                for key in cls.RESOURCE_KEYS:
                    if key in config:
                        path_value = config[key]
                        
                        if not path_value or not isinstance(path_value, str):
                            continue
                        
                        if key == 'subtree_path':
                            if path_value.startswith("./"):
                                abs_path = os.path.normpath(os.path.join(project_root, path_value[2:]))
                            else:
                                abs_path = os.path.abspath(path_value)
                            
                            if os.path.isdir(abs_path):
                                for root, dirs, files in os.walk(abs_path):
                                    for f in files:
                                        referenced_files.add(os.path.normpath(os.path.join(root, f)))
                            continue
                        
                        if path_value.startswith("./"):
                            abs_path = os.path.normpath(os.path.join(project_root, path_value[2:]))
                        else:
                            abs_path = os.path.abspath(path_value)
                        
                        if os.path.exists(abs_path):
                            referenced_files.add(abs_path)
        
        return referenced_files
    
    @classmethod
    def get_project_resource_dirs(cls) -> List[str]:
        """从 TYPE_DIR_MAP 自动生成资源目录列表，避免手动维护导致遗漏"""
        return list(set(cls.TYPE_DIR_MAP.values()))
    
    @classmethod
    def cleanup_unreferenced_files(cls, 
                                    project_root: str, 
                                    referenced_files: Set[str]) -> List[str]:
        removed_files = []
        
        if not project_root or not os.path.exists(project_root):
            return removed_files
        
        abs_project_root = os.path.abspath(project_root)
        abs_referenced = set(os.path.normpath(os.path.abspath(f)) for f in referenced_files)
        
        resource_dirs = cls.get_project_resource_dirs()
        
        for rel_dir in resource_dirs:
            abs_dir = os.path.normpath(os.path.join(abs_project_root, rel_dir))
            
            if not os.path.exists(abs_dir):
                continue
            
            for root, dirs, files in os.walk(abs_dir):
                for filename in files:
                    abs_file_path = os.path.normpath(os.path.join(root, filename))
                    
                    if abs_file_path not in abs_referenced:
                        try:
                            rel_path = os.path.relpath(abs_file_path, abs_project_root)
                            relative_path = f"./{rel_path.replace(os.sep, '/')}"
                            cache_result = cls.move_to_cache(relative_path, project_root)
                            if cache_result:
                                removed_files.append(abs_file_path)
                            else:
                                LogManager.debug_print(f"[WARN] 无法移动文件到缓存: {abs_file_path}")
                        except Exception as e:
                            LogManager.debug_print(f"[WARN] 清理未引用文件失败 {abs_file_path}: {e}")
        
        return removed_files
    
    @classmethod
    def detect_resource_type(cls, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        
        for resource_type, extensions in cls.RESOURCE_EXTENSIONS.items():
            if ext in extensions:
                return resource_type
        
        return 'other'
    
    @classmethod
    def is_resource_path(cls, path: str) -> bool:
        if not path or not isinstance(path, str):
            return False
        
        ext = os.path.splitext(path)[1].lower()
        
        all_extensions = []
        for extensions in cls.RESOURCE_EXTENSIONS.values():
            all_extensions.extend(extensions)
        
        return ext in all_extensions
    
    @classmethod
    def move_to_cache(cls, file_path: str, project_root: str) -> Optional[str]:
        if not file_path or not project_root:
            return None
        
        abs_project_root = os.path.abspath(project_root)
        
        abs_file_path = file_path
        if file_path.startswith("./"):
            abs_file_path = os.path.normpath(os.path.join(project_root, file_path[2:]))
        else:
            abs_file_path = os.path.abspath(file_path)
        
        if not os.path.exists(abs_file_path):
            return None
        
        if not cls.is_path_in_project(abs_file_path, abs_project_root):
            return None
        
        cache_dir = os.path.join(project_root, cls.CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        
        filename = os.path.basename(abs_file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(filename)
        cached_filename = f"{name}_{timestamp}{ext}"
        
        cache_path = os.path.join(cache_dir, cached_filename)
        
        try:
            shutil.move(abs_file_path, cache_path)
            return cache_path
        except Exception as e:
            LogManager.debug_print(f"[WARN] 移动文件到缓存失败: {e}")
            return None
    
    @classmethod
    def cleanup_cache(cls, project_root: str, max_age_days: int = 7) -> List[str]:
        """清理缓存目录中超过指定天数的文件
        
        Args:
            project_root: 项目根目录
            max_age_days: 最大保留天数，默认7天
            
        Returns:
            被清理的文件路径列表
        """
        cleaned_files = []
        
        if not project_root or not os.path.exists(project_root):
            return cleaned_files
        
        cache_dir = os.path.join(project_root, cls.CACHE_DIR)
        if not os.path.exists(cache_dir):
            return cleaned_files
        
        now = datetime.now().timestamp()
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        for filename in os.listdir(cache_dir):
            file_path = os.path.join(cache_dir, filename)
            
            if not os.path.isfile(file_path):
                continue
            
            try:
                file_mtime = os.path.getmtime(file_path)
                if now - file_mtime > max_age_seconds:
                    os.remove(file_path)
                    cleaned_files.append(file_path)
            except Exception as e:
                LogManager.debug_print(f"[WARN] 清理缓存文件失败 {file_path}: {e}")
        
        return cleaned_files
    
    @classmethod
    def move_dir_to_cache(cls, dir_path: str, project_root: str) -> Optional[str]:
        """将目录移动到缓存目录，而非直接删除
        
        Args:
            dir_path: 要移动的目录路径（绝对路径或相对路径）
            project_root: 项目根目录
            
        Returns:
            缓存路径，失败返回 None
        """
        if not dir_path or not project_root:
            return None
        
        abs_project_root = os.path.abspath(project_root)
        
        if dir_path.startswith("./"):
            abs_dir_path = os.path.normpath(os.path.join(project_root, dir_path[2:]))
        else:
            abs_dir_path = os.path.abspath(dir_path)
        
        if not os.path.exists(abs_dir_path):
            return None
        
        if not cls.is_path_in_project(abs_dir_path, abs_project_root):
            return None
        
        cache_dir = os.path.join(project_root, cls.CACHE_DIR)
        os.makedirs(cache_dir, exist_ok=True)
        
        dir_name = os.path.basename(abs_dir_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cached_dir_name = f"{dir_name}_{timestamp}"
        
        cache_path = os.path.join(cache_dir, cached_dir_name)
        
        try:
            shutil.move(abs_dir_path, cache_path)
            return cache_path
        except Exception as e:
            LogManager.debug_print(f"[WARN] 移动目录到缓存失败: {e}")
            return None
    
    @classmethod
    def import_single_file_to_project(cls,
                                       source_path: str,
                                       project_root: str,
                                       resource_type: str = None) -> Optional[str]:
        """将外部文件导入项目目录，若文件已在项目内则直接返回相对路径
        
        注意：不再自动移动旧文件到缓存。旧文件可能仍被其他节点引用，
        资源清理统一由 cleanup_unreferenced_files 在保存时处理。
        """
        if not os.path.exists(source_path):
            return None
        
        if not project_root or not os.path.exists(project_root):
            return None
        
        abs_project_root = os.path.abspath(project_root)
        abs_source_path = os.path.abspath(source_path)
        
        relative_path = None
        
        if cls.is_path_in_project(abs_source_path, abs_project_root):
            if source_path.startswith("./"):
                relative_path = source_path
            else:
                try:
                    rel_path = os.path.relpath(abs_source_path, abs_project_root)
                    relative_path = f"./{rel_path.replace(os.sep, '/')}"
                except Exception:
                    relative_path = source_path
        else:
            if resource_type is None:
                resource_type = cls.detect_resource_type(source_path)
            relative_path = cls._import_single_resource(abs_source_path, project_root, resource_type)
        
        return relative_path
    
    @classmethod
    def ensure_project_structure(cls, project_root: str) -> bool:
        if not project_root:
            return False
        
        try:
            for rel_dir in cls.get_project_resource_dirs():
                abs_dir = os.path.join(project_root, rel_dir)
                os.makedirs(abs_dir, exist_ok=True)
            
            cache_dir = os.path.join(project_root, cls.CACHE_DIR)
            os.makedirs(cache_dir, exist_ok=True)
            return True
        except Exception as e:
            LogManager.debug_print(f"[ERROR] 创建项目目录结构失败: {e}")
            return False
    
    @classmethod
    def save_with_cleanup(cls, tree_data: Dict[str, Any], project_root: str) -> Dict[str, Any]:
        """保存前的统一资源处理：导入外部资源 → 清理未引用文件 → 清理过期缓存
        
        Args:
            tree_data: 行为树数据
            project_root: 项目根目录
            
        Returns:
            可能更新了路径的 tree_data
        """
        if not project_root or not os.path.exists(project_root):
            return tree_data
        
        # 1. 导入项目外部的资源文件
        external_resources = cls.collect_external_resources(tree_data, project_root)
        if external_resources:
            path_mapping = cls.import_resources_to_project(external_resources, project_root)
            if path_mapping:
                tree_data = cls.update_tree_paths(tree_data, path_mapping)
        
        # 2. 清理未被引用的资源文件（移到缓存）
        referenced_files = cls.get_all_referenced_files(tree_data, project_root)
        cls.cleanup_unreferenced_files(project_root, referenced_files)
        
        # 3. 清理超过7天的缓存文件
        cls.cleanup_cache(project_root)
        
        return tree_data
