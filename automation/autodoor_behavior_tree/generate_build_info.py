#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
打包配置生成脚本

在打包前运行此脚本，根据 build_config.json 生成版本信息文件
"""

import json
import os
from datetime import datetime

def get_git_commit():
    """获取当前Git提交哈希"""
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""

def load_build_config():
    """加载打包配置"""
    config_file = os.path.join(os.path.dirname(__file__), 'build_config.json')
    
    if not os.path.exists(config_file):
        print(f"Warning: {config_file} not found, using default config")
        return {
            "version": "1.0.0",
            "expire_date": "2099-12-31",
            "force_update": False,
            "build_type": "release"
        }
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config

def generate_version_info():
    """生成版本信息文件"""
    config = load_build_config()
    
    build_type = config.get("build_type", "release")
    
    debug_config = {
        "enable_logging": build_type != "release",
        "log_level": "DEBUG" if build_type != "release" else "INFO",
        "enable_debug_mode": build_type != "release"
    }
    
    build_info = {
        "version": config.get("version", "1.0.0"),
        "expire_date": config.get("expire_date", "2099-12-31"),
        "force_update": config.get("force_update", False),
        "build_type": build_type,
        "build_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "git_commit": get_git_commit(),
        
        "github": config.get("github", {
            "owner": "wdhq4261761",
            "repo": "autodoor_behavior_tree"
        }),
        
        "update_links": config.get("update_links", {
            "tool_intro": "https://my.feishu.cn/wiki/Z2AAwPevRiavmwkFf3jcL0Emnye?from=from_copylink",
            "download": "https://my.feishu.cn/wiki/Z2AAwPevRiavmwkFf3jcL0Emnye?from=from_copylink",
            "changelog": "https://my.feishu.cn/wiki/Z2AAwPevRiavmwkFf3jcL0Emnye?from=from_copylink"
        }),
        
        "app_info": config.get("app_info", {
            "name": "AutoDoor Behavior Tree",
            "name_cn": "AutoDoor 行为树系统"
        }),
        
        "debug": debug_config
    }
    
    output_file = os.path.join(os.path.dirname(__file__), 'bt_utils', 'build_info.json')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(build_info, f, indent=2, ensure_ascii=False)
    
    print(f"Generated build_info.json:")
    print(f"  Version: {build_info['version']}")
    print(f"  Expire Date: {build_info['expire_date']}")
    print(f"  Force Update: {build_info['force_update']}")
    print(f"  Build Type: {build_info['build_type']}")
    print(f"  Build Time: {build_info['build_time']}")
    print(f"  Git Commit: {build_info['git_commit']}")
    print(f"  GitHub Owner: {build_info['github']['owner']}")
    print(f"  GitHub Repo: {build_info['github']['repo']}")
    print(f"  Debug Mode: {build_info['debug']['enable_debug_mode']}")
    
    return build_info

if __name__ == "__main__":
    generate_version_info()
