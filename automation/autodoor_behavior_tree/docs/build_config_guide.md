# 打包配置说明

## 概述

本项目使用 `build_config.json` 作为打包配置文件，用于控制客户端版本、过期时间、强制更新等参数。

## 配置文件

### build_config.json

位置：项目根目录

```json
{
    "version": "1.2.2a",
    "expire_date": "2026-05-21",
    "force_update": false,
    "build_type": "beta",
    
    "github": {
        "owner": "wdhq4261761",
        "repo": "autodoor_behavior_tree"
    },
    
    "update_links": {
        "tool_intro": "https://my.feishu.cn/wiki/...",
        "download": "https://my.feishu.cn/wiki/...",
        "changelog": "https://my.feishu.cn/wiki/..."
    },
    
    "app_info": {
        "name": "AutoDoor Behavior Tree",
        "name_cn": "AutoDoor 行为树系统"
    }
}
```

**注意**：只需要修改顶层配置项，`build_info` 部分会在打包时自动生成到 `bt_utils/build_info.json` 中。

### 配置项说明

#### 基础配置

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| version | string | 客户端版本号 | "1.2.2a", "1.3.0" |
| expire_date | string | 包体过期时间（YYYY-MM-DD） | "2026-05-21" |
| force_update | boolean | 是否强制更新 | true, false |
| build_type | string | 构建类型 | "beta", "release", "alpha" |

#### GitHub 配置

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| github.owner | string | GitHub 仓库所有者 | "wdhq4261761" |
| github.repo | string | GitHub 仓库名称 | "autodoor_behavior_tree" |

#### 更新链接配置

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| update_links.tool_intro | string | 工具介绍页面链接 | "https://..." |
| update_links.download | string | 下载页面链接 | "https://..." |
| update_links.changelog | string | 更新日志链接 | "https://..." |

#### 应用信息配置

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| app_info.name | string | 应用名称（英文） | "AutoDoor Behavior Tree" |
| app_info.name_cn | string | 应用名称（中文） | "AutoDoor 行为树系统" |

#### 调试配置（自动生成）

调试配置会根据 `build_type` 自动生成：

- **release 版本**：调试模式关闭
- **其他版本**（beta, alpha等）：调试模式开启

```json
{
    "debug": {
        "enable_logging": true,
        "log_level": "DEBUG",
        "enable_debug_mode": true
    }
}
```

## 使用方法

### 1. 修改配置文件

在打包前，修改 `build_config.json` 中的配置项：

```json
{
    "version": "1.3.0",
    "expire_date": "2026-06-30",
    "force_update": false,
    "build_type": "release"
}
```

### 2. 运行打包脚本

运行打包脚本时，会自动：
1. 读取 `build_config.json`
2. 生成 `bt_utils/build_info.json`
3. 将配置信息注入到客户端中

```bash
# DD版本（游戏版）
build_dd.bat

# 标准版本
build_standard.bat
```

### 3. 验证配置

打包完成后，可以在客户端中查看版本信息：
- 版本号会显示在标题栏
- 过期时间会在启动时检查
- 强制更新标记会在更新检查时生效

## 配置示例

### Beta测试版本

```json
{
    "version": "1.2.2a",
    "expire_date": "2026-05-21",
    "force_update": false,
    "build_type": "beta",
    
    "github": {
        "owner": "wdhq4261761",
        "repo": "autodoor_behavior_tree"
    },
    
    "update_links": {
        "tool_intro": "https://my.feishu.cn/wiki/...",
        "download": "https://my.feishu.cn/wiki/...",
        "changelog": "https://my.feishu.cn/wiki/..."
    },
    
    "app_info": {
        "name": "AutoDoor Behavior Tree",
        "name_cn": "AutoDoor 行为树系统"
    }
}
```

### 正式发布版本

```json
{
    "version": "1.3.0",
    "expire_date": "2099-12-31",
    "force_update": false,
    "build_type": "release",
    
    "github": {
        "owner": "wdhq4261761",
        "repo": "autodoor_behavior_tree"
    },
    
    "update_links": {
        "tool_intro": "https://my.feishu.cn/wiki/...",
        "download": "https://my.feishu.cn/wiki/...",
        "changelog": "https://my.feishu.cn/wiki/..."
    },
    
    "app_info": {
        "name": "AutoDoor Behavior Tree",
        "name_cn": "AutoDoor 行为树系统"
    }
}
```

### 强制更新版本

```json
{
    "version": "1.4.0",
    "expire_date": "2099-12-31",
    "force_update": true,
    "build_type": "release",
    
    "github": {
        "owner": "wdhq4261761",
        "repo": "autodoor_behavior_tree"
    },
    
    "update_links": {
        "tool_intro": "https://my.feishu.cn/wiki/...",
        "download": "https://my.feishu.cn/wiki/...",
        "changelog": "https://my.feishu.cn/wiki/..."
    },
    
    "app_info": {
        "name": "AutoDoor Behavior Tree",
        "name_cn": "AutoDoor 行为树系统"
    }
}
```

## 版本号格式

支持以下格式：
- 纯数字：`1.1.8`, `1.3.0`
- 带后缀：`1.1.1a`, `1.2.0beta`, `1.3.0rc1`

版本比较规则：
- `1.1.1a` < `1.1.1` < `1.1.1b` < `1.2.0beta` < `1.2.0`
- 字母后缀按字典序比较：`a` < `b` < `beta` < `rc`
- 有后缀的版本 < 无后缀的版本（正式版）

## 工作流程

```
build_config.json (手动修改)
        ↓
generate_build_info.py (自动生成)
        ↓
bt_utils/build_info.json (运行时读取)
        ↓
客户端启动 (加载配置)
```

## 注意事项

1. **版本号格式**：建议使用纯数字格式（如 `1.3.0`），便于版本比较
2. **过期时间**：Beta版本建议设置较短的过期时间，正式版本可设置为 `2099-12-31`
3. **强制更新**：仅在需要强制用户更新时设置为 `true`，配合GitHub Release的 `[FORCE_UPDATE]` 标记使用
4. **构建类型**：`beta` 用于测试版本，`release` 用于正式发布
5. **GitHub配置**：确保仓库地址正确，否则版本检查功能无法正常工作
6. **更新链接**：确保链接有效，用户点击"使用文档"等按钮时会跳转到这些链接
7. **调试模式**：调试配置会根据 `build_type` 自动生成，无需手动配置

## 相关文件

- `build_config.json` - 打包配置文件（手动修改）
- `generate_build_info.py` - 配置生成脚本（自动运行）
- `bt_utils/build_info.json` - 运行时配置文件（自动生成）
- `main.py` - 主程序入口（读取配置）
- `bt_utils/version_checker.py` - 版本检查器（读取配置）
