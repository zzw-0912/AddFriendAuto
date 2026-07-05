use std::collections::HashMap;
use std::fs::OpenOptions;
use std::io::{BufRead, BufReader, Write};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use serde::{Deserialize, Serialize};
use tauri::{Emitter, Manager};

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
    #[serde(default)]
    executable_path: String,
    display_name: String,
}

#[derive(Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct WeChatWindowBinding {
    #[serde(default)]
    slot_id: i64,
    hwnd: u64,
    pid: u32,
    title: String,
    display_name: String,
    #[serde(default)]
    executable_path: String,
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
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn hide_child_console(command: &mut Command) {
    #[cfg(windows)]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }
}

fn log_timestamp() -> String {
    match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(duration) => format!("unix_ms={}", duration.as_millis()),
        Err(_) => "unix_ms=0".to_string(),
    }
}

fn append_client_log(message: impl AsRef<str>) {
    let logs_dir = data_dir().join("logs");
    let _ = std::fs::create_dir_all(&logs_dir);
    let log_path = logs_dir.join("friendauto_client.txt");
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = writeln!(file, "[{}] {}", log_timestamp(), message.as_ref());
    }
}

fn summarize_task_config(config_json: &str) -> String {
    let Ok(value) = serde_json::from_str::<serde_json::Value>(config_json) else {
        return format!("invalid_json bytes={}", config_json.len());
    };
    let run_id = value.get("run_id").or_else(|| value.get("task_id"));
    let slot_id = value.get("slot_id");
    let target_count = value
        .get("targets")
        .and_then(|targets| targets.as_array())
        .map(|targets| targets.len())
        .unwrap_or(0);
    let target_type = value
        .get("target_type")
        .and_then(|target_type| target_type.as_str())
        .unwrap_or("");
    format!(
        "run_id={:?} slot_id={:?} target_type={} targets={} bytes={}",
        run_id,
        slot_id,
        target_type,
        target_count,
        config_json.len()
    )
}

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

fn bundled_runtime_dir(app_handle: &tauri::AppHandle) -> Option<PathBuf> {
    let resource_dir = app_handle
        .path()
        .resource_dir()
        .ok()
        .map(|path| path.join("friendauto_runtime"));
    match &resource_dir {
        Some(path) => append_client_log(format!(
            "bundled_runtime_dir candidate={} exists={}",
            path.display(),
            path.is_dir()
        )),
        None => append_client_log("bundled_runtime_dir unavailable"),
    }
    resource_dir.filter(|path| path.is_dir())
}

fn resolve_worker_path(app_handle: &tauri::AppHandle) -> Result<PathBuf, String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let mut candidates = Vec::new();
    if let Some(runtime_dir) = bundled_runtime_dir(app_handle) {
        candidates.push(runtime_dir.join("scripts").join("platform_worker.exe"));
    }
    candidates.extend([
        cwd.join("..").join("scripts").join("platform_worker.exe"),
        cwd.join("..").join("..").join("scripts").join("platform_worker.exe"),
        cwd.join("scripts").join("platform_worker.exe"),
        cwd.join("..").join("scripts").join("platform_worker.py"),
        cwd.join("..").join("..").join("scripts").join("platform_worker.py"),
        cwd.join("scripts").join("platform_worker.py"),
    ]);

    for candidate in candidates {
        append_client_log(format!(
            "resolve_worker_path check={} exists={}",
            candidate.display(),
            candidate.is_file()
        ));
        if candidate.is_file() {
            append_client_log(format!("resolve_worker_path selected={}", candidate.display()));
            return Ok(candidate);
        }
    }

    append_client_log("resolve_worker_path failed: worker not found");
    Err("未找到内置 platform_worker.exe 或外置 scripts/platform_worker.py".to_string())
}

fn is_worker_executable(path: &Path) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| value.eq_ignore_ascii_case("exe"))
        .unwrap_or(false)
}

fn run_powershell(script: &str) -> Result<String, String> {
    let mut command = Command::new("powershell");
    hide_child_console(&mut command);
    append_client_log(format!("run_powershell start script_bytes={}", script.len()));
    let output = command
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ])
        .output()
        .map_err(|e| {
            append_client_log(format!("run_powershell spawn_error={}", e));
            format!("PowerShell 启动失败: {}", e)
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        append_client_log(format!(
            "run_powershell failed status={:?} stderr={}",
            output.status.code(),
            stderr
        ));
        return Err(if stderr.is_empty() {
            "PowerShell 命令执行失败".to_string()
        } else {
            stderr
        });
    }

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    append_client_log(format!(
        "run_powershell ok status={:?} stdout_bytes={}",
        output.status.code(),
        stdout.len()
    ));
    Ok(stdout)
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
        let executable_path = item
            .get("executablePath")
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
            executable_path,
            display_name,
        });
    }
    Ok(windows)
}

fn is_wechat_window(window: &WeChatWindowInfo) -> bool {
    let process_name = window.process_name.to_ascii_lowercase();
    let title = window.title.to_ascii_lowercase();
    process_name.contains("wechat")
        || process_name.contains("weixin")
        || title.contains("wechat")
        || title.contains("weixin")
        || window.title.contains("微信")
}

fn binding_from_window(window: &WeChatWindowInfo, previous: &WeChatWindowBinding) -> WeChatWindowBinding {
    WeChatWindowBinding {
        slot_id: previous.slot_id,
        hwnd: window.hwnd,
        pid: window.pid,
        title: window.title.clone(),
        display_name: window.display_name.clone(),
        executable_path: window.executable_path.clone(),
        bound_at: previous.bound_at.clone(),
    }
}

fn find_best_wechat_window(
    windows: &[WeChatWindowInfo],
    binding: &WeChatWindowBinding,
) -> Option<WeChatWindowInfo> {
    let binding_process = binding.display_name.to_ascii_lowercase();
    let binding_title = binding.title.to_ascii_lowercase();
    let binding_path = binding.executable_path.to_ascii_lowercase();

    windows
        .iter()
        .filter(|window| is_wechat_window(window))
        .map(|window| {
            let mut score = 1;
            if window.pid == binding.pid {
                score += 100;
            }
            if !binding_path.is_empty()
                && !window.executable_path.is_empty()
                && window.executable_path.eq_ignore_ascii_case(&binding.executable_path)
            {
                score += 80;
            }
            let window_process = window.process_name.to_ascii_lowercase();
            if !window_process.is_empty() && binding_process.contains(&window_process) {
                score += 25;
            }
            let window_title = window.title.to_ascii_lowercase();
            if !binding_title.is_empty()
                && (window_title == binding_title
                    || window_title.contains(&binding_title)
                    || binding_title.contains(&window_title))
            {
                score += 15;
            }
            (score, window.clone())
        })
        .max_by_key(|(score, _)| *score)
        .map(|(_, window)| window)
}

fn push_unique_path(paths: &mut Vec<PathBuf>, path: PathBuf) {
    if path.is_file() && !paths.iter().any(|item| item.eq(&path)) {
        paths.push(path);
    }
}

fn collect_named_exe_under(paths: &mut Vec<PathBuf>, root: &Path, names: &[&str], depth: usize) {
    if depth == 0 || !root.is_dir() {
        return;
    }
    let Ok(entries) = std::fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_file() {
            let Some(file_name) = path.file_name().and_then(|name| name.to_str()) else {
                continue;
            };
            if names.iter().any(|name| file_name.eq_ignore_ascii_case(name)) {
                push_unique_path(paths, path);
            }
        } else if path.is_dir() {
            collect_named_exe_under(paths, &path, names, depth - 1);
        }
    }
}

fn common_wechat_executable_candidates(binding: &WeChatWindowBinding) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if !binding.executable_path.trim().is_empty() {
        push_unique_path(&mut candidates, PathBuf::from(binding.executable_path.trim()));
    }

    let roots = [
        std::env::var_os("ProgramFiles"),
        std::env::var_os("ProgramFiles(x86)"),
        std::env::var_os("LOCALAPPDATA"),
        std::env::var_os("APPDATA"),
    ];
    for root in roots.into_iter().flatten() {
        let root = PathBuf::from(root);
        for candidate in [
            root.join("Tencent").join("WeChat").join("WeChat.exe"),
            root.join("Tencent").join("Weixin").join("Weixin.exe"),
            root.join("Tencent").join("微信").join("WeChat.exe"),
        ] {
            push_unique_path(&mut candidates, candidate);
        }
        collect_named_exe_under(
            &mut candidates,
            &root.join("Tencent"),
            &["WeChat.exe", "Weixin.exe"],
            4,
        );
    }

    candidates
}

fn registry_wechat_executable_candidates() -> Vec<PathBuf> {
    let script = r#"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$paths = New-Object System.Collections.Generic.List[string]
$keys = @(
  'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
foreach ($key in $keys) {
  Get-ItemProperty $key -ErrorAction SilentlyContinue | ForEach-Object {
    $name = [string]($_.DisplayName)
    if ($name -notlike '*WeChat*' -and $name -notlike '*微信*' -and $name -notlike '*Weixin*') { return }
    foreach ($value in @($_.DisplayIcon, $_.InstallLocation)) {
      if ([string]::IsNullOrWhiteSpace([string]$value)) { continue }
      $text = ([string]$value).Trim('"')
      if ($text -match '\.exe') {
        $exe = $text -replace ',\d+$',''
        if (Test-Path $exe) { $paths.Add($exe) }
      } elseif (Test-Path (Join-Path $text 'WeChat.exe')) {
        $paths.Add((Join-Path $text 'WeChat.exe'))
      } elseif (Test-Path (Join-Path $text 'Weixin.exe')) {
        $paths.Add((Join-Path $text 'Weixin.exe'))
      }
    }
  }
}
$paths | Select-Object -Unique | ConvertTo-Json -Compress
"#;
    let Ok(stdout) = run_powershell(script) else {
        return Vec::new();
    };
    if stdout.trim().is_empty() {
        return Vec::new();
    }
    let Ok(value) = serde_json::from_str::<serde_json::Value>(&stdout) else {
        return Vec::new();
    };
    let values = match value {
        serde_json::Value::Array(items) => items,
        serde_json::Value::String(_) => vec![value],
        _ => Vec::new(),
    };
    values
        .into_iter()
        .filter_map(|item| item.as_str().map(PathBuf::from))
        .filter(|path| path.is_file())
        .collect()
}

fn launch_wechat(binding: &WeChatWindowBinding) -> bool {
    let mut candidates = common_wechat_executable_candidates(binding);
    candidates.extend(registry_wechat_executable_candidates());
    for candidate in candidates {
        append_client_log(format!("launch_wechat candidate={}", candidate.display()));
        if Command::new(&candidate).spawn().is_ok() {
            append_client_log(format!("launch_wechat spawned={}", candidate.display()));
            return true;
        }
    }

    append_client_log("launch_wechat fallback_uri=weixin://");
    Command::new("explorer")
        .arg("weixin://")
        .spawn()
        .or_else(|_| Command::new("explorer").arg("wechat://").spawn())
        .is_ok()
}

fn activate_wechat_window(binding: &WeChatWindowBinding) {
    let script = format!(
        r#"
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class FriendAutoActivateWin32 {{
  [DllImport("user32.dll")]
  public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);
}}
"@
$hwnd = [IntPtr]::new({hwnd})
[void][FriendAutoActivateWin32]::ShowWindow($hwnd, 9)
[void][FriendAutoActivateWin32]::SetForegroundWindow($hwnd)
"#,
        hwnd = binding.hwnd
    );
    if let Err(error) = run_powershell(&script) {
        append_client_log(format!("activate_wechat_window failed={}", error));
    }
}

fn list_wechat_windows_internal() -> Result<Vec<WeChatWindowInfo>, String> {
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
  $executablePath = ""
  try {
    $process = Get-Process -Id $processId -ErrorAction Stop
    $processName = [string]$process.ProcessName
    $executablePath = [string]$process.Path
  } catch {}

  if ($title -like '*微信*' -or $title -like '*WeChat*' -or $title -like '*Weixin*' -or $processName -like '*WeChat*' -or $processName -like '*Weixin*') {
    $items.Add(
      [pscustomobject]@{
        hwnd = [int64]$hwnd.ToInt64()
        pid = [int]$processId
        title = [string]$title
        processName = [string]$processName
        executablePath = [string]$executablePath
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

fn validate_wechat_binding_internal(binding: &WeChatWindowBinding) -> Result<bool, String> {
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

fn ensure_wechat_binding_internal(
    binding: WeChatWindowBinding,
) -> Result<WeChatWindowBinding, String> {
    append_client_log(format!(
        "ensure_wechat_binding start slot={} hwnd={} pid={} path={}",
        binding.slot_id, binding.hwnd, binding.pid, binding.executable_path
    ));
    if validate_wechat_binding_internal(&binding).unwrap_or(false) {
        activate_wechat_window(&binding);
        append_client_log("ensure_wechat_binding existing_ok");
        return Ok(binding);
    }

    if let Ok(windows) = list_wechat_windows_internal() {
        if let Some(window) = find_best_wechat_window(&windows, &binding) {
            let recovered = binding_from_window(&window, &binding);
            activate_wechat_window(&recovered);
            append_client_log(format!(
                "ensure_wechat_binding recovered_open hwnd={} pid={}",
                recovered.hwnd, recovered.pid
            ));
            return Ok(recovered);
        }
    }

    let launched = launch_wechat(&binding);
    append_client_log(format!("ensure_wechat_binding launched={}", launched));
    for attempt in 1..=25 {
        std::thread::sleep(Duration::from_millis(800));
        let Ok(windows) = list_wechat_windows_internal() else {
            continue;
        };
        if let Some(window) = find_best_wechat_window(&windows, &binding) {
            let recovered = binding_from_window(&window, &binding);
            activate_wechat_window(&recovered);
            append_client_log(format!(
                "ensure_wechat_binding recovered_after_launch attempt={} hwnd={} pid={}",
                attempt, recovered.hwnd, recovered.pid
            ));
            return Ok(recovered);
        }
    }

    append_client_log("ensure_wechat_binding failed");
    Err("无法自动打开微信，请确认本机已安装微信并登录，或先在“我的”页面重新绑定微信窗口".to_string())
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
    let mut command = Command::new("wmic");
    hide_child_console(&mut command);
    append_client_log("get_machine_code start");
    let output = command
        .args(["csproduct", "get", "uuid"])
        .output()
        .ok();
    if let Some(out) = output {
        if out.status.success() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            for line in stdout.lines() {
                let trimmed = line.trim();
                if !trimmed.is_empty() && trimmed != "UUID" {
                    append_client_log(format!("get_machine_code ok value={}", trimmed));
                    return trimmed.to_string();
                }
            }
        }
    }
    append_client_log("get_machine_code fallback unknown-machine");
    "unknown-machine".to_string()
}

#[tauri::command]
fn list_wechat_windows() -> Result<Vec<WeChatWindowInfo>, String> {
    return list_wechat_windows_internal();

/*
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
*/
}

#[tauri::command]
fn validate_wechat_binding(binding: WeChatWindowBinding) -> Result<bool, String> {
    return validate_wechat_binding_internal(&binding);

/*
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
*/
}

#[tauri::command]
fn ensure_wechat_binding(binding: WeChatWindowBinding) -> Result<WeChatWindowBinding, String> {
    ensure_wechat_binding_internal(binding)
}

fn prepare_task_config_json(config_json: &str) -> Result<String, String> {
    let mut value: serde_json::Value = serde_json::from_str(config_json).map_err(|e| e.to_string())?;
    let slot_id = value.get("slot_id").and_then(|v| v.as_i64()).unwrap_or(1);
    let binding_value = value
        .get("wechat_binding")
        .or_else(|| value.get("wechatBinding"))
        .cloned();

    if let Some(binding_value) = binding_value {
        let mut binding: WeChatWindowBinding =
            serde_json::from_value(binding_value).map_err(|e| e.to_string())?;
        if binding.slot_id <= 0 {
            binding.slot_id = slot_id;
        }
        let binding = ensure_wechat_binding_internal(binding)?;
        if let Some(object) = value.as_object_mut() {
            object.insert(
                "wechat_binding".to_string(),
                serde_json::to_value(binding).map_err(|e| e.to_string())?,
            );
        }
    }

    Ok(value.to_string())
}

#[tauri::command]
fn start_task(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, Mutex<TaskState>>,
    config_json: String,
) -> Result<(), String> {
    let config_json = prepare_task_config_json(&config_json)?;
    append_client_log(format!(
        "start_task requested {}",
        summarize_task_config(&config_json)
    ));
    let (run_id, slot_id) = task_identity(&config_json)?;
    let mut state = state.lock().map_err(|e| e.to_string())?;
    clear_stop_request(&run_id);

    if let Some(mut child) = state.children.remove(&run_id) {
        let _ = child.kill();
        let _ = child.wait();
    }

    let script_path = resolve_worker_path(&app_handle)?;
    append_client_log(format!(
        "start_task worker={} is_exe={}",
        script_path.display(),
        is_worker_executable(&script_path)
    ));

    let mut command = if is_worker_executable(&script_path) {
        Command::new(&script_path)
    } else {
        let mut command = Command::new("python");
        command.arg(&script_path);
        command
    };
    hide_child_console(&mut command);

    let mut child = command
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| {
            append_client_log(format!(
                "start_task spawn_error worker={} error={}",
                script_path.display(),
                e
            ));
            format!("Failed to start script: {}", e)
        })?;
    append_client_log(format!("start_task spawned pid={}", child.id()));

    if let Some(mut stdin) = child.stdin.take() {
        stdin.write_all(config_json.as_bytes()).map_err(|e| {
            append_client_log(format!("start_task stdin_write_error={}", e));
            e.to_string()
        })?;
        append_client_log(format!("start_task stdin_written bytes={}", config_json.len()));
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
                    append_client_log(format!("worker_stdout {}", trimmed));
                    let payload = enrich_script_payload(&trimmed, &stdout_run_id, slot_id);
                    let _ = app.emit("script-event", payload);
                }
            }
        }
        append_client_log(format!("worker_stdout_closed run_id={}", stdout_run_id));
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
                        append_client_log(format!("worker_stderr {}", trimmed));
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
    append_client_log(format!("stop_task requested run_id={}", run_id));
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
fn write_client_log(message: String) -> Result<(), String> {
    let sanitized: String = message.chars().take(2000).collect();
    append_client_log(format!("frontend {}", sanitized));
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
            ensure_wechat_binding,
            start_task,
            stop_task,
            write_client_log,
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
