//! Quant OS Pro — Tauri desktop entry.
//!
//! Responsibilities:
//! * wire the trial/license commands (see [`license`]) into the Tauri runtime,
//! * register the `opener` plugin (the subscription screen opens the external checkout),
//! * launch the bundled Python FastAPI backend as a **managed sidecar** on startup and
//!   terminate it on exit, so the shipped `.app`/`.dmg` runs self-contained.
//!
//! The sidecar launch is **best-effort**: if the binary is absent (e.g. `tauri dev`
//! before it has been built) the app still runs — the license gate is pure Rust/JS, and
//! the dashboards simply show "API not reachable" until a backend is available.

mod license;

use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Holds the spawned Python API sidecar so it can be terminated when the app exits.
struct ApiSidecar(Mutex<Option<CommandChild>>);

/// Launch the bundled `quant-os-api` sidecar (best-effort).
fn spawn_sidecar(app: &tauri::AppHandle) {
    // Give the backend a writable data dir inside Application Support so its cache and
    // (optional) registry DB persist between launches. sidecar_entry.py reads QOS_DATA_DIR
    // and maps it onto the QUANTLAB_* settings the API resolves paths from.
    let data_env = app.path().app_data_dir().ok().map(|dir| {
        let backend = dir.join("backend");
        let _ = std::fs::create_dir_all(&backend);
        backend.to_string_lossy().to_string()
    });

    let cmd = match app.shell().sidecar("binaries/quant-os-api") {
        Ok(c) => c,
        Err(e) => {
            eprintln!("[quant-os] no API sidecar ({e}); run the backend manually in dev.");
            return;
        }
    };
    let cmd = match data_env {
        Some(d) => cmd.env("QOS_DATA_DIR", d),
        None => cmd,
    };
    // Pass the bundled read-only data dir (registry DB + result plots) so the backend can
    // seed them into the writable dir on first run → the .app ships self-contained data.
    let cmd = match app.path().resource_dir() {
        Ok(res) => cmd.env(
            "QOS_BUNDLE_DIR",
            res.join("resources").to_string_lossy().to_string(),
        ),
        Err(_) => cmd,
    };
    match cmd.spawn() {
        Ok((_rx, child)) => {
            if let Some(state) = app.try_state::<ApiSidecar>() {
                *state.0.lock().unwrap() = Some(child);
            }
            eprintln!("[quant-os] API sidecar started on http://127.0.0.1:8000");
        }
        Err(e) => eprintln!("[quant-os] API sidecar failed to start: {e}"),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(ApiSidecar(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![
            license::get_status,
            license::activate_license,
            license::recheck_license,
        ])
        .setup(|app| {
            spawn_sidecar(app.handle());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Quant OS Pro")
        .run(|app, event| {
            // Kill the API sidecar when the app is closing so it doesn't linger.
            if let RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app.try_state::<ApiSidecar>() {
                    if let Some(child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            }
        });
}
