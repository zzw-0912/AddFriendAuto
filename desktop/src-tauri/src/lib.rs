use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use serde::{Deserialize, Serialize};
use tauri::Emitter;

#[derive(Serialize, Deserialize)]
struct StoredData {
    token: String,
    email: String,
}

struct TaskState {
    child: Option<Child>,
}

fn data_dir() -> PathBuf {
    let path = dirs_next::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("FriendAuto");
    std::fs::create_dir_all(&path).ok();
    path
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
fn start_task(
    app_handle: tauri::AppHandle,
    state: tauri::State<'_, Mutex<TaskState>>,
    config_json: String,
) -> Result<(), String> {
    let mut state = state.lock().map_err(|e| e.to_string())?;

    if let Some(mut child) = state.child.take() {
        let _ = child.kill();
        let _ = child.wait();
    }

    let script_path = std::env::current_dir()
        .map_err(|e| e.to_string())?
        .join("..")
        .join("scripts")
        .join("test_autobot.py");

    let mut child = Command::new("python")
        .arg(script_path.to_str().unwrap_or(""))
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

    std::thread::spawn(move || {
        for line in reader.lines() {
            if let Ok(line) = line {
                let trimmed = line.trim().to_string();
                if !trimmed.is_empty() {
                    let _ = app.emit("script-event", trimmed);
                }
            }
        }
        let _ = app.emit("script-event", r#"{"event":"exited"}"#);
    });

    state.child = Some(child);
    Ok(())
}

#[tauri::command]
fn stop_task(state: tauri::State<'_, Mutex<TaskState>>) -> Result<(), String> {
    let mut state = state.lock().map_err(|e| e.to_string())?;
    if let Some(mut child) = state.child.take() {
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Mutex::new(TaskState { child: None }))
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
            start_task,
            stop_task,
            save_token,
            load_token,
            clear_token,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
