use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
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

fn safe_run_id(value: &str) -> String {
    let mut text: String = value
        .trim()
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '.' | '_' | '-') {
                ch
            } else {
                '_'
            }
        })
        .take(80)
        .collect();
    if text.is_empty() {
        text = "manual".to_string();
    }
    text
}

fn stop_request_path(run_id: &str) -> PathBuf {
    let dir = data_dir().join("stop_requests");
    std::fs::create_dir_all(&dir).ok();
    dir.join(format!("{}.stop", safe_run_id(run_id)))
}

fn write_stop_request(run_id: &str) -> Result<(), String> {
    let path = stop_request_path(run_id);
    std::fs::write(path, "stop").map_err(|e| e.to_string())
}

fn clear_stop_request(run_id: &str) {
    let path = stop_request_path(run_id);
    let _ = std::fs::remove_file(path);
}

const LEGACY_AUTODOOR_SOURCE_PATH: &str = r"D:\AddFriend\autodoor_behavior_tree";
const LEGACY_PROJECT_PATH: &str = r"D:\AddFriend\Addfriend";
const LEGACY_EDITOR_EXECUTABLE_PATH: &str = r"D:\AddFriend\autodoor_behavior_tree\dist\autodoor-behaviortree-1.6.0\autodoor-behaviortree-1.6.0.exe";

fn autodoor_editor_path(source_path: &Path) -> String {
    let preferred = source_path
        .join("dist")
        .join("autodoor-behaviortree-1.6.0")
        .join("autodoor-behaviortree-1.6.0.exe");
    if preferred.is_file() {
        preferred.to_string_lossy().to_string()
    } else {
        String::new()
    }
}

fn runtime_base_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        dirs.push(cwd.clone());
        if let Some(parent) = cwd.parent() {
            dirs.push(parent.to_path_buf());
            if let Some(grandparent) = parent.parent() {
                dirs.push(grandparent.to_path_buf());
            }
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            dirs.push(exe_dir.to_path_buf());
            if let Some(parent) = exe_dir.parent() {
                dirs.push(parent.to_path_buf());
            }
        }
    }
    dirs
}

fn local_autodoor_config() -> Option<AutoDoorConfig> {
    for base in runtime_base_dirs() {
        for root in [base.join("automation"), base.clone()] {
            let source_path = root.join("autodoor_behavior_tree");
            let project_path = root.join("Addfriend");
            if source_path.is_dir() && project_path.is_dir() {
                return Some(AutoDoorConfig {
                    editor_executable_path: autodoor_editor_path(&source_path),
                    autodoor_source_path: source_path.to_string_lossy().to_string(),
                    project_path: project_path.to_string_lossy().to_string(),
                });
            }
        }
    }
    None
}

fn legacy_autodoor_config() -> AutoDoorConfig {
    AutoDoorConfig {
        autodoor_source_path: LEGACY_AUTODOOR_SOURCE_PATH.to_string(),
        project_path: LEGACY_PROJECT_PATH.to_string(),
        editor_executable_path: LEGACY_EDITOR_EXECUTABLE_PATH.to_string(),
    }
}

fn is_legacy_path(value: &str, legacy: &str) -> bool {
    value.trim().eq_ignore_ascii_case(legacy)
}

fn default_autodoor_config() -> AutoDoorConfig {
    local_autodoor_config().unwrap_or_else(legacy_autodoor_config)
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
    } else if is_legacy_path(&config.autodoor_source_path, LEGACY_AUTODOOR_SOURCE_PATH)
        && Path::new(&defaults.autodoor_source_path).is_dir()
        && !is_legacy_path(&defaults.autodoor_source_path, LEGACY_AUTODOOR_SOURCE_PATH)
    {
        config.autodoor_source_path = defaults.autodoor_source_path;
    }
    if config.project_path.is_empty() {
        config.project_path = defaults.project_path;
    } else if is_legacy_path(&config.project_path, LEGACY_PROJECT_PATH)
        && Path::new(&defaults.project_path).is_dir()
        && !is_legacy_path(&defaults.project_path, LEGACY_PROJECT_PATH)
    {
        config.project_path = defaults.project_path;
    }
    if config.editor_executable_path.is_empty()
        || (is_legacy_path(&config.editor_executable_path, LEGACY_EDITOR_EXECUTABLE_PATH)
            && !is_legacy_path(&defaults.editor_executable_path, LEGACY_EDITOR_EXECUTABLE_PATH))
    {
        config.editor_executable_path = defaults.editor_executable_path;
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
Add-Type -TypeDefinition @"
using System;
using System.Text;
using System.Runtime.InteropServices;

public static class FriendAutoWin32 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

  [DllImport("user32.dll")]
  public static extern bool IsWindowVisible(IntPtr hWnd);

  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern int GetWindowTextLengthW(IntPtr hWnd);

  [DllImport("user32.dll", CharSet = CharSet.Unicode)]
  public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder text, int count);

  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

$items = [System.Collections.Generic.List[object]]::new()
$callback = [FriendAutoWin32+EnumWindowsProc]{
  param([IntPtr]$hwnd, [IntPtr]$lparam)
  if (-not [FriendAutoWin32]::IsWindowVisible($hwnd)) { return $true }
  $length = [FriendAutoWin32]::GetWindowTextLengthW($hwnd)
  if ($length -le 0) { return $true }

  $buffer = [System.Text.StringBuilder]::new($length + 1)
  [void][FriendAutoWin32]::GetWindowTextW($hwnd, $buffer, $buffer.Capacity)
  $title = $buffer.ToString()
  if ([string]::IsNullOrWhiteSpace($title)) { return $true }

  [uint32]$processId = 0
  [void][FriendAutoWin32]::GetWindowThreadProcessId($hwnd, [ref]$processId)
  $processName = ""
  try {
    $processName = [string](Get-Process -Id $processId -ErrorAction Stop).ProcessName
  } catch {}

  if ($title -like '*微信*' -or $title -like '*WeChat*' -or $title -like '*Weixin*' -or $processName -like '*WeChat*' -or $processName -like '*Weixin*') {
    $items.Add(
      [pscustomobject]@{
        hwnd = [int64]$hwnd.ToInt64()
        pid = [int]$processId
        title = [string]$title
        processName = [string]$processName
      }
    )
  }
  return $true
}

[void][FriendAutoWin32]::EnumWindows($callback, [IntPtr]::Zero)
$items = @($items | Sort-Object pid, hwnd)
$items | ConvertTo-Json -Compress
"#;
    let stdout = run_powershell(script)?;
    parse_wechat_windows(&stdout)
}

#[tauri::command]
fn validate_wechat_binding(binding: WeChatWindowBinding) -> Result<bool, String> {
    let script = format!(
        r#"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class FriendAutoValidateWin32 {{
  [DllImport("user32.dll")]
  public static extern bool IsWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}}
"@

$hwnd = [IntPtr]::new({hwnd})
$expectedProcessId = [uint32]{pid}
if (-not [FriendAutoValidateWin32]::IsWindow($hwnd)) {{
  "false"
  exit
}}

[uint32]$actualProcessId = 0
[void][FriendAutoValidateWin32]::GetWindowThreadProcessId($hwnd, [ref]$actualProcessId)
if ($actualProcessId -eq $expectedProcessId) {{ "true" }} else {{ "false" }}
"#,
        hwnd = binding.hwnd,
        pid = binding.pid
    );
    let stdout = run_powershell(&script)?;
    Ok(stdout.trim().eq_ignore_ascii_case("true"))
}

#[tauri::command]
fn start_task(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, Mutex<TaskState>>,
    config_json: String,
) -> Result<(), String> {
    let (run_id, slot_id) = task_identity(&config_json)?;
    let mut state = state.lock().map_err(|e| e.to_string())?;
    clear_stop_request(&run_id);

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
    let _ = write_stop_request(&run_id);
    let mut state = state.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = state.children.remove(&run_id) {
        for _ in 0..20 {
            match child.try_wait() {
                Ok(Some(_)) => return Ok(()),
                Ok(None) => std::thread::sleep(Duration::from_millis(100)),
                Err(_) => break,
            }
        }
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
