use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use serde::{Deserialize, Serialize};
use tauri::Emitter;

#[derive(Serialize, Deserialize)]
struct StoredData {
    token: String,
    email: String,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct AutoDoorConfig {
    autodoor_source_path: String,
    project_path: String,
    #[serde(default)]
    editor_executable_path: String,
}

struct TaskState {
    children: HashMap<String, Child>,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct WeChatWindowInfo {
    hwnd: u64,
    pid: u32,
    title: String,
    process_name: String,
    display_name: String,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct WeChatWindowBinding {
    hwnd: u64,
    pid: u32,
    title: String,
    display_name: String,
    #[serde(default)]
    bound_at: String,
}

fn data_dir() -> PathBuf {
    let path = dirs_next::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("FriendAuto");
    std::fs::create_dir_all(&path).ok();
    path
}

fn default_autodoor_config() -> AutoDoorConfig {
    AutoDoorConfig {
        autodoor_source_path: r"D:\AddFriend\autodoor_behavior_tree".to_string(),
        project_path: r"D:\AddFriend\Addfriend".to_string(),
        editor_executable_path: r"D:\AddFriend\autodoor_behavior_tree\dist\autodoor-behaviortree-1.6.0\autodoor-behaviortree-1.6.0.exe".to_string(),
    }
}

fn autodoor_config_path() -> PathBuf {
    data_dir().join("autodoor.json")
}

fn normalize_autodoor_config(mut config: AutoDoorConfig) -> AutoDoorConfig {
    let defaults = default_autodoor_config();
    config.autodoor_source_path = config.autodoor_source_path.trim().to_string();
    config.project_path = config.project_path.trim().to_string();
    config.editor_executable_path = config.editor_executable_path.trim().to_string();

    if config.autodoor_source_path.is_empty() {
        config.autodoor_source_path = defaults.autodoor_source_path;
    }
    if config.project_path.is_empty() {
        config.project_path = defaults.project_path;
    }
    config
}

fn validate_autodoor_config(config: &AutoDoorConfig) -> Result<(), String> {
    let source_path = Path::new(&config.autodoor_source_path);
    if !source_path.is_dir() {
        return Err(format!("AutoDoor 源码目录不存在: {}", config.autodoor_source_path));
    }

    let project_path = Path::new(&config.project_path);
    if !project_path.is_dir() {
        return Err(format!("AutoDoor 项目目录不存在: {}", config.project_path));
    }
    if !project_path.join("project.json").is_file() || !project_path.join("tree.json").is_file() {
        return Err("AutoDoor 项目必须包含 project.json 和 tree.json".to_string());
    }

    if !config.editor_executable_path.is_empty() {
        let editor_path = Path::new(&config.editor_executable_path);
        if !editor_path.exists() {
            return Err(format!("AutoDoor 编辑器路径不存在: {}", config.editor_executable_path));
        }
    }

    Ok(())
}

fn resolve_worker_path() -> Result<PathBuf, String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let candidates = [
        cwd.join("..").join("scripts").join("platform_worker.py"),
        cwd.join("..").join("..").join("scripts").join("platform_worker.py"),
        cwd.join("scripts").join("platform_worker.py"),
    ];

    for candidate in candidates {
        if candidate.is_file() {
            return Ok(candidate);
        }
    }

    Err("未找到 scripts/platform_worker.py".to_string())
}

fn run_powershell(script: &str) -> Result<String, String> {
    let output = Command::new("powershell")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ])
        .output()
        .map_err(|e| format!("PowerShell 启动失败: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if stderr.is_empty() {
            "PowerShell 命令执行失败".to_string()
        } else {
            stderr
        });
    }

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn parse_wechat_windows(stdout: &str) -> Result<Vec<WeChatWindowInfo>, String> {
    if stdout.trim().is_empty() {
        return Ok(Vec::new());
    }

    let value: serde_json::Value = serde_json::from_str(stdout).map_err(|e| e.to_string())?;
    let values = match value {
        serde_json::Value::Array(items) => items,
        serde_json::Value::Object(_) => vec![value],
        serde_json::Value::Null => Vec::new(),
        _ => return Ok(Vec::new()),
    };

    let mut windows = Vec::new();
    for item in values {
        let hwnd = item.get("hwnd").and_then(|v| v.as_u64()).unwrap_or(0);
        let pid = item.get("pid").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        let title = item.get("title").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let process_name = item
            .get("processName")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        if hwnd == 0 || pid == 0 || title.trim().is_empty() {
            continue;
        }
        let display_name = format!("{} (PID: {}, HWND: {})", title, pid, hwnd);
        windows.push(WeChatWindowInfo {
            hwnd,
            pid,
            title,
            process_name,
            display_name,
        });
    }
    Ok(windows)
}

fn enrich_script_payload(raw: &str, run_id: &str, slot_id: i64) -> String {
    let mut value = serde_json::from_str::<serde_json::Value>(raw).unwrap_or_else(|_| {
        serde_json::json!({
            "event": "output",
            "message": raw,
        })
    });

    if let Some(object) = value.as_object_mut() {
        object
            .entry("run_id".to_string())
            .or_insert_with(|| serde_json::Value::String(run_id.to_string()));
        object
            .entry("slot_id".to_string())
            .or_insert_with(|| serde_json::Value::Number(slot_id.into()));
    }

    value.to_string()
}

fn task_identity(config_json: &str) -> Result<(String, i64), String> {
    let value: serde_json::Value = serde_json::from_str(config_json).map_err(|e| e.to_string())?;
    let run_id = value
        .get("run_id")
        .and_then(|v| v.as_str())
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
        .or_else(|| {
            value.get("task_id").and_then(|v| {
                if let Some(id) = v.as_i64() {
                    Some(id.to_string())
                } else {
                    v.as_str().map(|s| s.to_string())
                }
            })
        })
        .ok_or_else(|| "任务配置缺少 run_id".to_string())?;
    let slot_id = value.get("slot_id").and_then(|v| v.as_i64()).unwrap_or(1);
    Ok((run_id, slot_id))
}

fn resolve_editor_executable(path: &str) -> Result<PathBuf, String> {
    let editor_path = PathBuf::from(path);
    if editor_path.is_file() {
        return Ok(editor_path);
    }
    if editor_path.is_dir() {
        let preferred = editor_path.join("autodoor-behaviortree-1.6.0.exe");
        if preferred.is_file() {
            return Ok(preferred);
        }
        let entries = std::fs::read_dir(&editor_path).map_err(|e| e.to_string())?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|ext| ext.to_str()).is_some_and(|ext| ext.eq_ignore_ascii_case("exe")) {
                return Ok(path);
            }
        }
    }
    Err("未找到可执行的 AutoDoor 编辑器 exe".to_string())
}

#[tauri::command]
fn get_machine_code() -> String {
    let output = Command::new("wmic")
        .args(["csproduct", "get", "uuid"])
        .output()
        .ok();
    if let Some(out) = output {
        if out.status.success() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            for line in stdout.lines() {
                let trimmed = line.trim();
                if !trimmed.is_empty() && trimmed != "UUID" {
                    return trimmed.to_string();
                }
            }
        }
    }
    "unknown-machine".to_string()
}

#[tauri::command]
fn list_wechat_windows() -> Result<Vec<WeChatWindowInfo>, String> {
    let script = r#"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$items = Get-Process |
  Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } |
  Where-Object { $_.MainWindowTitle -like '*微信*' -or $_.ProcessName -like '*WeChat*' } |
  Sort-Object Id |
  ForEach-Object {
    [pscustomobject]@{
      hwnd = [int64]$_.MainWindowHandle
      pid = [int]$_.Id
      title = [string]$_.MainWindowTitle
      processName = [string]$_.ProcessName
    }
  }
$items | ConvertTo-Json -Compress
"#;
    let stdout = run_powershell(script)?;
    parse_wechat_windows(&stdout)
}

#[tauri::command]
fn validate_wechat_binding(binding: WeChatWindowBinding) -> Result<bool, String> {
    let windows = list_wechat_windows()?;
    Ok(windows
        .iter()
        .any(|window| window.hwnd == binding.hwnd && window.pid == binding.pid))
}

#[tauri::command]
fn start_task(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, Mutex<TaskState>>,
    config_json: String,
) -> Result<(), String> {
    let (run_id, slot_id) = task_identity(&config_json)?;
    let mut state = state.lock().map_err(|e| e.to_string())?;

    if let Some(mut child) = state.children.remove(&run_id) {
        let _ = child.kill();
        let _ = child.wait();
    }

    let script_path = resolve_worker_path()?;

    let mut child = Command::new("python")
        .arg(&script_path)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start script: {}", e))?;

    if let Some(mut stdin) = child.stdin.take() {
        stdin.write_all(config_json.as_bytes()).map_err(|e| e.to_string())?;
    }

    let stdout = child.stdout.take().ok_or("No stdout")?;
    let reader = BufReader::new(stdout);
    let app = app_handle.clone();
    let stdout_run_id = run_id.clone();

    std::thread::spawn(move || {
        for line in reader.lines() {
            if let Ok(line) = line {
                let trimmed = line.trim().to_string();
                if !trimmed.is_empty() {
                    let payload = enrich_script_payload(&trimmed, &stdout_run_id, slot_id);
                    let _ = app.emit("script-event", payload);
                }
            }
        }
        let payload = serde_json::json!({
            "event": "exited",
            "run_id": stdout_run_id,
            "slot_id": slot_id,
        })
        .to_string();
        let _ = app.emit("script-event", payload);
    });

    if let Some(stderr) = child.stderr.take() {
        let err_reader = BufReader::new(stderr);
        let err_app = app_handle.clone();
        let err_run_id = run_id.clone();
        std::thread::spawn(move || {
            for line in err_reader.lines() {
                if let Ok(line) = line {
                    let trimmed = line.trim().to_string();
                    if !trimmed.is_empty() {
                        let payload = serde_json::json!({
                            "event": "error",
                            "message": trimmed,
                            "run_id": err_run_id,
                            "slot_id": slot_id,
                        })
                        .to_string();
                        let _ = err_app.emit("script-event", payload);
                    }
                }
            }
        });
    }

    state.children.insert(run_id, child);
    Ok(())
}

#[tauri::command]
fn stop_task(state: tauri::State<'_, Mutex<TaskState>>, run_id: String) -> Result<(), String> {
    let mut state = state.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = state.children.remove(&run_id) {
        let _ = child.kill();
        let _ = child.wait();
    }
    Ok(())
}

#[tauri::command]
fn save_token(token: String, email: String) -> Result<(), String> {
    let stored = StoredData { token, email };
    let path = data_dir().join("auth.json");
    let json = serde_json::to_string(&stored).map_err(|e| e.to_string())?;
    std::fs::write(&path, json).map_err(|e| e.to_string())
}

#[tauri::command]
fn load_token() -> Result<Option<StoredData>, String> {
    let path = data_dir().join("auth.json");
    if !path.exists() {
        return Ok(None);
    }
    let json = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let stored: StoredData = serde_json::from_str(&json).map_err(|e| e.to_string())?;
    Ok(Some(stored))
}

#[tauri::command]
fn clear_token() -> Result<(), String> {
    let path = data_dir().join("auth.json");
    if path.exists() {
        std::fs::remove_file(&path).map_err(|e| e.to_string())
    } else {
        Ok(())
    }
}

#[tauri::command]
fn load_autodoor_config() -> Result<AutoDoorConfig, String> {
    let path = autodoor_config_path();
    if !path.exists() {
        return Ok(default_autodoor_config());
    }

    let json = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let config: AutoDoorConfig = serde_json::from_str(&json).map_err(|e| e.to_string())?;
    Ok(normalize_autodoor_config(config))
}

#[tauri::command]
fn save_autodoor_config(config: AutoDoorConfig) -> Result<AutoDoorConfig, String> {
    let config = normalize_autodoor_config(config);
    validate_autodoor_config(&config)?;

    let path = autodoor_config_path();
    let json = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    std::fs::write(&path, json).map_err(|e| e.to_string())?;
    Ok(config)
}

#[tauri::command]
fn open_autodoor_editor(config: AutoDoorConfig) -> Result<(), String> {
    let config = normalize_autodoor_config(config);
    if config.editor_executable_path.is_empty() {
        return Err("请先填写 AutoDoor 编辑器路径".to_string());
    }
    let executable = resolve_editor_executable(&config.editor_executable_path)?;
    Command::new(executable)
        .arg(&config.project_path)
        .spawn()
        .map_err(|e| format!("启动 AutoDoor 编辑器失败: {}", e))?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Mutex::new(TaskState { children: HashMap::new() }))
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_machine_code,
            list_wechat_windows,
            validate_wechat_binding,
            start_task,
            stop_task,
            save_token,
            load_token,
            clear_token,
            load_autodoor_config,
            save_autodoor_config,
            open_autodoor_editor,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
