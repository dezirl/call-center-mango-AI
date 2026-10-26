use std::net::TcpListener;
#[cfg(all(not(debug_assertions), windows))]
use std::os::windows::process::CommandExt;
#[cfg(not(debug_assertions))]
use std::{
    io,
    process::{Child, Command},
    sync::{Arc, Mutex},
};
#[cfg(not(debug_assertions))]
use tauri::{path::BaseDirectory, Manager, RunEvent};

struct BackendPort(u16);

#[tauri::command]
fn backend_port(state: tauri::State<'_, BackendPort>) -> u16 {
    state.0
}

fn find_free_port() -> Result<u16, String> {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|listener| listener.local_addr())
        .map(|address| address.port())
        .map_err(|error| format!("Could not find a free local port: {error}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let port = find_free_port().expect("Could not find a free local port");
    #[cfg(not(debug_assertions))]
    let backend_process: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    #[cfg(not(debug_assertions))]
    let backend_process_for_setup = Arc::clone(&backend_process);

    tauri::Builder::default()
        .manage(BackendPort(port))
        .invoke_handler(tauri::generate_handler![backend_port])
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            #[cfg(debug_assertions)]
            let _ = app;
            #[cfg(not(debug_assertions))]
            {
                let resource_backend = app
                    .path()
                    .resolve(
                        "backend/voicebridge-backend/voicebridge-backend.exe",
                        BaseDirectory::Resource,
                    )
                    .ok()
                    .filter(|path| path.is_file());
                let portable_backend = std::env::current_exe()?
                    .parent()
                    .ok_or_else(|| {
                        io::Error::new(io::ErrorKind::NotFound, "Application directory is missing.")
                    })?
                    .join("backend/voicebridge-backend/voicebridge-backend.exe");
                let backend = resource_backend.unwrap_or(portable_backend);
                if !backend.is_file() {
                    return Err(io::Error::new(
                        io::ErrorKind::NotFound,
                        format!(
                            "Voice Bridge backend was not found at {}.",
                            backend.display()
                        ),
                    )
                    .into());
                }
                let backend_dir = backend.parent().ok_or_else(|| {
                    io::Error::new(io::ErrorKind::NotFound, "Backend directory is missing.")
                })?;
                let mut backend_command = Command::new(&backend);
                backend_command
                    .current_dir(backend_dir)
                    .arg("--host")
                    .arg("127.0.0.1")
                    .arg("--port")
                    .arg(port.to_string());
                #[cfg(windows)]
                backend_command.creation_flags(0x00000010); // CREATE_NEW_CONSOLE
                let child = backend_command.spawn()?;
                if let Ok(mut process) = backend_process_for_setup.lock() {
                    *process = Some(child);
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Voice Bridge")
        .run(move |_app_handle, _event| {
            #[cfg(not(debug_assertions))]
            if let RunEvent::Exit = _event {
                if let Ok(mut process) = backend_process.lock() {
                    if let Some(mut child) = process.take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}
