use std::process::Command;

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
        .invoke_handler(tauri::generate_handler![run_python_script])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
