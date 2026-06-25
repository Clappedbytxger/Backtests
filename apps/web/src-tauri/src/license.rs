//! Trial & subscription engine for Quant OS Pro.
//!
//! State machine (single source of truth, persisted encrypted in the macOS
//! Application Support directory `~/Library/Application Support/com.quantos.pro/license.dat`):
//!
//! * **TRIAL**    — first launch stamps an encrypted timestamp; the app is fully
//!                  unlocked for [`TRIAL_DAYS`] days.
//! * **EXPIRED**  — `now - first_launch >= TRIAL_DAYS` and no active license. The
//!                  frontend hard-walls the whole UI behind the subscription screen.
//! * **LICENSED** — a Lemon Squeezy license key validated as `status == "active"`.
//!
//! ## Honest security note
//! This is a **local, offline** gate. The vault is encrypted at rest with AES-256-GCM
//! (authenticated — a tampered file fails to decrypt), but the key is embedded in the
//! binary, so this is *obfuscation*, not cryptographic protection against a determined
//! user (who can delete the vault file to reset the trial, or patch the binary). That is
//! the inherent limit of every offline trial. For real anti-piracy the trial state and
//! license must be validated server-side. This implementation is the correct shape for
//! an MVP and matches what the Lemon Squeezy desktop-licensing flow expects.

use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    Aes256Gcm, Key, Nonce,
};
use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};

/// Length of the free trial.
const TRIAL_DAYS: u64 = 7;
const TRIAL_SECONDS: u64 = TRIAL_DAYS * 24 * 60 * 60;
const SECONDS_PER_DAY: u64 = 24 * 60 * 60;

/// Embedded AES-256 key (exactly 32 bytes — the `&[u8; 32]` type pins the length at
/// compile time). Obfuscation-grade only; see the module note.
const ENC_KEY: &[u8; 32] = b"qos_pro_v1_local_vault_key_32byt";

/// Lemon Squeezy license validation endpoint (only needs the license key).
const LS_VALIDATE_URL: &str = "https://api.lemonsqueezy.com/v1/licenses/validate";

/// The persisted, encrypted vault contents.
#[derive(Serialize, Deserialize, Default, Clone)]
struct Vault {
    /// Unix seconds of the very first launch (stamped once, never overwritten).
    first_launch: Option<u64>,
    /// The last successfully validated license key (if any).
    license_key: Option<String>,
    /// Whether the last validation reported an active subscription.
    licensed: bool,
}

/// JSON payload returned to the frontend guard.
#[derive(Serialize, Clone)]
pub struct StatusReport {
    /// One of `"TRIAL" | "EXPIRED" | "LICENSED"`.
    status: String,
    /// Whole days left in the trial; `-1` when LICENSED, `0` when EXPIRED.
    days_remaining: i64,
    /// The configured trial length, so the UI can show "X / 7".
    trial_total_days: u64,
    /// The active license key (only set when LICENSED), for display/echo.
    license_key: Option<String>,
}

// ── time + storage helpers ───────────────────────────────────────────────────

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn vault_path(app: &AppHandle) -> Result<PathBuf, String> {
    // On macOS this resolves to ~/Library/Application Support/<identifier>/.
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("license.dat"))
}

fn encrypt(plaintext: &[u8]) -> Result<String, String> {
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(ENC_KEY));
    let nonce = Aes256Gcm::generate_nonce(&mut OsRng); // 96-bit random nonce
    let ciphertext = cipher
        .encrypt(&nonce, plaintext)
        .map_err(|e| format!("encrypt failed: {e}"))?;
    // Store as base64(nonce || ciphertext+tag).
    let mut blob = nonce.to_vec();
    blob.extend_from_slice(&ciphertext);
    Ok(STANDARD.encode(blob))
}

fn decrypt(b64: &str) -> Result<Vec<u8>, String> {
    let blob = STANDARD.decode(b64.trim()).map_err(|e| e.to_string())?;
    if blob.len() < 12 + 16 {
        return Err("vault too short".into());
    }
    let (nonce_bytes, ciphertext) = blob.split_at(12);
    let cipher = Aes256Gcm::new(Key::<Aes256Gcm>::from_slice(ENC_KEY));
    cipher
        .decrypt(Nonce::from_slice(nonce_bytes), ciphertext)
        .map_err(|_| "vault decrypt/auth failed".into())
}

/// Load the vault, or a fresh default if it is missing/unreadable/tampered.
fn load_vault(app: &AppHandle) -> Vault {
    let Ok(path) = vault_path(app) else {
        return Vault::default();
    };
    let Ok(raw) = fs::read_to_string(&path) else {
        return Vault::default();
    };
    match decrypt(&raw).and_then(|bytes| serde_json::from_slice(&bytes).map_err(|e| e.to_string())) {
        Ok(v) => v,
        Err(_) => Vault::default(),
    }
}

fn save_vault(app: &AppHandle, v: &Vault) -> Result<(), String> {
    let json = serde_json::to_vec(v).map_err(|e| e.to_string())?;
    let enc = encrypt(&json)?;
    let path = vault_path(app)?;
    fs::write(&path, enc).map_err(|e| e.to_string())
}

/// Pure status derivation from a vault (no I/O).
fn compute_status(v: &Vault) -> StatusReport {
    if v.licensed && v.license_key.is_some() {
        return StatusReport {
            status: "LICENSED".into(),
            days_remaining: -1,
            trial_total_days: TRIAL_DAYS,
            license_key: v.license_key.clone(),
        };
    }
    let start = v.first_launch.unwrap_or_else(now_secs);
    // saturating_sub guards a backwards-set system clock.
    let elapsed = now_secs().saturating_sub(start);
    if elapsed >= TRIAL_SECONDS {
        StatusReport {
            status: "EXPIRED".into(),
            days_remaining: 0,
            trial_total_days: TRIAL_DAYS,
            license_key: None,
        }
    } else {
        let remaining = TRIAL_SECONDS - elapsed;
        // ceil division → "Noch 1 Tag" until the very last second.
        let days = ((remaining + SECONDS_PER_DAY - 1) / SECONDS_PER_DAY) as i64;
        StatusReport {
            status: "TRIAL".into(),
            days_remaining: days,
            trial_total_days: TRIAL_DAYS,
            license_key: None,
        }
    }
}

// ── Lemon Squeezy validation ─────────────────────────────────────────────────

/// POST the key to Lemon Squeezy and report whether it is a *currently active*
/// subscription license. Returns `Ok(true)` only when the API says `valid == true`
/// AND the license `status == "active"` (so a cancelled/expired sub fails closed).
async fn ls_validate(key: &str) -> Result<bool, String> {
    let client = reqwest::Client::new();
    let resp = client
        .post(LS_VALIDATE_URL)
        .header("Accept", "application/json")
        .form(&[("license_key", key)])
        .send()
        .await
        .map_err(|e| format!("Netzwerkfehler bei der Lizenzprüfung: {e}"))?;
    let body: serde_json::Value = resp
        .json()
        .await
        .map_err(|e| format!("Unlesbare Antwort der Lizenz-API: {e}"))?;
    let valid = body.get("valid").and_then(|x| x.as_bool()).unwrap_or(false);
    let status = body
        .get("license_key")
        .and_then(|lk| lk.get("status"))
        .and_then(|s| s.as_str())
        .unwrap_or("");
    Ok(valid && status == "active")
}

// ── Tauri commands (invoked from the React guard) ────────────────────────────

/// Read the current gate status; stamps the first-launch timestamp on first ever call.
#[tauri::command]
pub fn get_status(app: AppHandle) -> StatusReport {
    let mut v = load_vault(&app);
    if v.first_launch.is_none() {
        v.first_launch = Some(now_secs());
        let _ = save_vault(&app, &v);
    }
    compute_status(&v)
}

/// Validate a license key against Lemon Squeezy and, on success, persist it →
/// flips the gate to LICENSED. Returns an error string the UI can show on failure.
#[tauri::command]
pub async fn activate_license(app: AppHandle, key: String) -> Result<StatusReport, String> {
    let key = key.trim().to_string();
    if key.is_empty() {
        return Err("Bitte gib einen Lizenzschlüssel ein.".into());
    }
    let active = ls_validate(&key).await?;
    let mut v = load_vault(&app);
    if v.first_launch.is_none() {
        v.first_launch = Some(now_secs());
    }
    if active {
        v.licensed = true;
        v.license_key = Some(key);
        save_vault(&app, &v)?;
        Ok(compute_status(&v))
    } else {
        v.licensed = false;
        v.license_key = None;
        let _ = save_vault(&app, &v);
        Err("Lizenz ungültig oder Abonnement nicht aktiv.".into())
    }
}

/// Re-validate a stored license on startup (catches a cancelled/expired subscription).
///
/// Fail policy: an explicit "inactive" response downgrades to EXPIRED immediately; a
/// *network* error keeps the current state (grace period) so a paying customer is not
/// locked out while offline. Flip the `Err(_)` arm to revoke if you prefer strict mode.
#[tauri::command]
pub async fn recheck_license(app: AppHandle) -> StatusReport {
    let mut v = load_vault(&app);
    if let Some(key) = v.license_key.clone() {
        match ls_validate(&key).await {
            Ok(true) => {
                v.licensed = true;
                let _ = save_vault(&app, &v);
            }
            Ok(false) => {
                v.licensed = false;
                v.license_key = None;
                let _ = save_vault(&app, &v);
            }
            Err(_) => { /* offline / transient — keep current state (grace) */ }
        }
    }
    if v.first_launch.is_none() {
        v.first_launch = Some(now_secs());
        let _ = save_vault(&app, &v);
    }
    compute_status(&v)
}
