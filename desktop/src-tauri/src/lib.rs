use std::path::PathBuf;
use std::process::Command;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
struct StoredData {
    token: String,
    email: String,
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
    // Use Windows WMIC to get a stable machine identifier
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
fn run_python_script(run_id: String) -> Result<String, String> {
    let script_path = std::env::current_dir()
        .map_err(|e| e.to_string())?
        .join("..")
        .join("scripts")
        .join("test_autobot.py");

    let output = Command::new("python")
        .arg(script_path.to_str().unwrap_or(""))
        .arg(&run_id)
        .output()
        .map_err(|e| format!("Failed to run script: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!("Script error: {}", stderr));
    }

    Ok(stdout)
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
            run_python_script,
            save_token,
            load_token,
            clear_token,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
