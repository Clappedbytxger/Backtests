# Quant OS Pro — Komplettanleitung: Desktop-App bauen (macOS & Windows)

Diese Anleitung führt dich Schritt für Schritt zu einer fertigen, **autarken** Desktop-App
mit **7-Tage-Trial → Hard-Wall → Lemon-Squeezy-Abo** und eingebautem Python-Backend. Für
Einsteiger geschrieben — du kannst sie von oben nach unten abarbeiten.

> **macOS oder Windows?** Die Abschnitte **1–12 beschreiben den macOS-Build** (`.dmg`).
> Der **Windows-Build** (`.exe`-Installer) steht in **Abschnitt 13** — gleicher Code,
> gleiches Gate, nur andere Toolchain. Ein `.dmg` baust du nur auf einem Mac, einen
> `.exe`-Installer nur auf Windows.

> **Warum auf dem Mac?** Eine macOS-`.app`/`.dmg` lässt sich nur auf einem Mac bauen
> (Xcode + Rust). Alle Dateien sind fertig vorbereitet; die Befehle führst du auf dem Mac
> aus.

**Was inzwischen fertig ist (du musst es nicht mehr bauen):**
- ✅ Tauri-Desktop-Wrapper (Apple-Silicon-Konfig, `.app`+`.dmg`)
- ✅ Trial-Engine (verschlüsselter Zeitstempel im Application-Support-Ordner)
- ✅ Lemon-Squeezy-Lizenzprüfung + Hard-Wall-Subscription-Screen
- ✅ **Beide dynamischen Routen export-fähig** (`strategies/[num]`, `academy/[moduleId]`) →
  der `.dmg`-Build läuft jetzt ohne Sonderschritt durch
- ✅ **Python-Backend als Sidecar** verdrahtet — die App startet das Backend selbst und
  beendet es beim Schließen

---

## Inhaltsübersicht

1. Voraussetzungen auf dem Mac installieren
2. Das Projekt auf den Mac bringen
3. Python-Umgebung (venv) einrichten
4. Node-Abhängigkeiten installieren
5. Pflicht-Konfiguration (4 Stellen)
6. Den Trial- & Hard-Gate testen (schnell, ohne Build)
7. Das Python-Backend als Sidecar bauen (autark)
8. Die `.dmg` bauen
9. Welche Daten die App braucht (online vs. gebündelt)
10. Sicherheits-Ehrlichkeit
11. Fehlerbehebung
12. Befehls-Schnellreferenz

---

## 1. Voraussetzungen auf dem Mac installieren

Öffne das **Terminal** (⌘+Leertaste → „Terminal") und führe nacheinander aus:

```bash
# (a) Xcode Command Line Tools — liefert Compiler & Codesign
xcode-select --install

# (b) Rust über rustup — die Sprache des Tauri-Wrappers
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# Terminal schließen & neu öffnen, dann das Apple-Silicon-Target sicherstellen:
rustup target add aarch64-apple-darwin

# (c) Node.js LTS (für das Frontend). Falls noch nicht vorhanden, via Homebrew:
#     /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
#     brew install node

# (d) Python 3 ist auf dem Mac vorinstalliert; prüfen:
python3 --version
```

Optional, aber empfohlen: **Ollama** (für den lokalen Agentenschwarm), falls du die
Swarm-Funktion live nutzen willst — `brew install ollama && ollama pull llama3`.

---

## 2. Das Projekt auf den Mac bringen

**Empfohlen: via Git** (sauber, ohne Müll-Ordner). Auf dem Windows-PC einmalig pushen,
auf dem Mac klonen.

Auf dem **Mac**:

```bash
# Ziel-Ordner deiner Wahl, z.B. ~/Projects
cd ~/Projects
git clone <DEINE_REPO_URL> Backtests
cd Backtests
```

**Alternative: direkt kopieren** (USB/Netzwerk). Wenn du den Ordner kopierst, **lasse diese
Unterordner weg** (sie sind betriebssystem-spezifisch und werden auf dem Mac neu gebaut):

```
.venv/                              ← Windows-Python, neu anlegen
apps/web/node_modules/             ← neu via npm install
apps/web/.next/                    ← Build-Cache
apps/web/out/                      ← Build-Output
apps/web/src-tauri/target/         ← Rust-Build-Cache
```

---

## 3. Python-Umgebung (venv) einrichten

Das Backend braucht seine Python-Pakete. Im Repo-Wurzelordner (`Backtests/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r apps/api/requirements-api.txt
```

Das installiert die schlanke, mac-taugliche Backend-Liste (pandas, scipy, scikit-learn,
lightgbm, yfinance, FastAPI … — **ohne** torch/LLM, die das Backend nicht braucht).

**Test, dass das Backend startet:**

```bash
.venv/bin/python -m uvicorn apps.api.main:app --port 8000
# Browser: http://localhost:8000/health  → {"status":"ok",...}
# Stoppen mit Ctrl-C
```

---

## 4. Node-Abhängigkeiten installieren

```bash
cd apps/web
npm install
```

Das zieht automatisch die Tauri-Pakete (`@tauri-apps/api`, `@tauri-apps/plugin-opener`,
`@tauri-apps/cli`, `cross-env`) mit.

---

## 5. Pflicht-Konfiguration (4 Stellen)

Bevor du an echte Kunden ausgibst, diese vier Dinge anpassen:

| # | Was | Datei | Stelle |
|---|---|---|---|
| 1 | **Verkaufs-/Checkout-URL** | `apps/web/lib/license.tsx` | `BUY_URL` → deine Lemon-Squeezy-URL |
| 2 | **App-Identifier** (optional) | `apps/web/src-tauri/tauri.conf.json` | `"identifier"` → deine Reverse-Domain |
| 3 | **Vault-Schlüssel** (empfohlen) | `apps/web/src-tauri/src/license.rs` | `ENC_KEY` (32 Bytes) → eigener Wert |
| 4 | **App-Icon** | — | `cd apps/web && npm run tauri icon /pfad/logo.png` |

**Im Lemon-Squeezy-Dashboard:** Für dein Abo-Produkt **„License keys" aktivieren**. Die
Validierung im Code braucht keinen API-Key — der Endpoint `…/v1/licenses/validate` nimmt
nur den Lizenzschlüssel. Bei Kündigung/Ablauf setzt Lemon Squeezy den Status automatisch
von `active` auf `expired`/`disabled`; die App fällt dann beim nächsten Start auf EXPIRED.

---

## 6. Den Trial- & Hard-Gate testen (schnell, ohne kompletten Build)

Das ist der schnellste Weg, das Hard-Gate selbst zu erleben — die App läuft in einem
**echten nativen Fenster**, das Frontend kommt vom Next-Dev-Server (alle Seiten gehen).

```bash
cd apps/web
npm run desktop:dev
```

> In diesem schnellen Dev-Modus startet das eingebettete Backend noch nicht (der Platzhalter
> ist keine echte Binary). Für volle Dashboard-Daten startest du das Backend in einem
> zweiten Terminal: `cd .. && .venv/bin/python -m uvicorn apps.api.main:app --port 8000`.
> Das **Gate** funktioniert auch ohne Backend.

**„7 Tage vergangen" simulieren** (ohne zu warten): in
`apps/web/src-tauri/src/license.rs` die Zeile

```rust
const TRIAL_DAYS: u64 = 7;
```

kurz auf `0` setzen → nächster `npm run desktop:dev` zeigt sofort den **EXPIRED**-Screen.
Danach zurück auf `7`. Oder den Vault löschen für eine frische Trial:

```bash
rm ~/Library/Application\ Support/com.quantos.pro/license.dat
```

**Lizenz-Aktivierung testen:** Auf dem EXPIRED-Screen einen echten Lizenzschlüssel
einfügen → **Aktivieren**. Bei `valid && status=="active"` schaltet die App auf LICENSED.

---

## 7. Das Python-Backend als Sidecar bauen (autark)

Damit die fertige `.dmg` das Backend **selbst startet** (ohne dass jemand Python
installieren muss), wird die API einmalig zu einer eigenständigen Binary „eingefroren".

```bash
# Repo-Wurzel, venv aktiv:
source .venv/bin/activate
bash scripts/build_sidecar_mac.sh
```

Das erzeugt (dauert ein paar Minuten, Binary ist mehrere hundert MB):

```
apps/web/src-tauri/binaries/quant-os-api-aarch64-apple-darwin
```

…und ersetzt damit den Text-Platzhalter. Die Tauri-App startet diese Binary künftig beim
Öffnen automatisch (auf `127.0.0.1:8000`) und beendet sie beim Schließen.

> **Ehrliche Hinweise zum Sidecar:**
> - Die Binary ist groß (pandas/scipy/scikit-learn/lightgbm werden mitgebündelt). torch und
>   LLM-Backends sind bewusst ausgeschlossen.
> - Die **Entwickler-Routen** des Agenten (`/agent/run`, `/agent/promote`, Slider-Eval)
>   starten Subprozesse (`python`, `git`) und funktionieren in einer eingefrorenen Binary
>   **nicht** — sie sind für die kommerzielle App irrelevant. Die Entscheidungs-Desks
>   (Registry, Regime, COT, Saisonalität, Risiko, Swarm, Switchboard, Live-Book) laufen.
> - Schlägt das Einfrieren an einem fehlenden Modul fehl: das Paket in
>   `apps/api/requirements-api.txt` ergänzen, `pip install`, und die `--collect`/`--exclude`-
>   Flags in `scripts/build_sidecar_mac.sh` anpassen.

---

## 8. Die `.dmg` bauen

```bash
cd apps/web
# Icon einmalig erzeugen, falls noch nicht geschehen:
npm run tauri icon /pfad/zu/logo.png
# Apple-Silicon-Build:
npm run desktop:build
```

Ergebnis:

```
apps/web/src-tauri/target/aarch64-apple-darwin/release/bundle/
├── macos/Quant OS Pro.app
└── dmg/Quant OS Pro_0.1.0_aarch64.dmg
```

Per Doppelklick installieren und das Hard-Gate wie ein Endkunde testen.

> **Reihenfolge wichtig:** erst Schritt 7 (Sidecar bauen) **und** das Daten-Bundling aus
> Abschnitt 9 (`bash scripts/bundle_data.sh`), **dann** Schritt 8 — sonst bündelt Tauri den
> Text-Platzhalter bzw. eine App ohne Registry-Daten.
>
> **Gatekeeper-Warnung:** Eine nicht-signierte App meldet beim ersten Start „nicht
> verifiziert". Für deinen eigenen Test: Rechtsklick auf die App → **Öffnen**. Für die
> Weitergabe an fremde Macs ohne Warnung brauchst du **Code-Signing + Notarization** (Apple-
> Developer-Konto, 99 $/Jahr) — ein separater, späterer Schritt.

---

## 9. Daten in der App (jetzt automatisch gebündelt)

Die `.dmg` startet **vollständig autark mit Daten** — du musst nichts mehr von Hand
kopieren. Zwei Klassen:

- **Live online** (kein Bundling nötig): Wetter-Radar, COT-Positionierung, Saisonalität,
  Risiko-Desk, Swarm — holen Marktdaten zur Laufzeit (yfinance/CFTC). Der Sidecar cached
  nach `~/Library/Application Support/com.quantos.pro/backend/data/`.
- **Gebündelte Registry** (Dashboard-Tabelle + Strategie-Detailseiten mit Plots): die
  Datei `strategies.db` (~0,8 MB) und die Plot-PNGs `strategies/*/results/*.png` (~15 MB)
  werden als Tauri-`resources` in die `.app` gepackt. Beim **ersten Start** kopiert der
  Sidecar sie automatisch in den schreibbaren Backend-Ordner (`QOS_BUNDLE_DIR` →
  `QUANTLAB_*`).

**Was du dafür tust — ein zusätzlicher Schritt vor dem `.dmg`-Build:**

```bash
# (falls strategies.db fehlt — regeneriert sie aus den Strategie-Ordnern:)
.venv/bin/python scripts/build_registry.py

# Daten in das Bundle-Verzeichnis kopieren:
bash scripts/bundle_data.sh
```

Das füllt `apps/web/src-tauri/resources/` (die Daten dort sind git-ignoriert). Danach
ganz normal `npm run desktop:build`. Die 155 Plots + die Registry sind dann in der `.dmg`
enthalten und ab dem ersten Öffnen sichtbar.

---

## 10. Sicherheits-Ehrlichkeit (bitte lesen)

- **Offline-Trial ist umgehbar.** Der Vault ist AES-256-GCM-verschlüsselt (manipulierte
  Datei = ungültig), aber der Schlüssel steckt in der App → das ist *Obfuskation*. Wer die
  Vault-Datei löscht, bekommt eine neue Trial. Das ist die prinzipielle Grenze jeder
  Offline-Trial; für echten Schutz müsste der Trial-Start server-seitig liegen.
- **Die Lizenzprüfung ist robust** (server-validiert über Lemon Squeezy) — ein gekündigtes
  Abo sperrt beim nächsten Online-Start zuverlässig.
- **Fail-Policy** der Lizenz-Neuprüfung: „inaktiv" → sofort EXPIRED; reiner Netzwerkfehler →
  aktueller Zustand bleibt (Kulanz für Offline-Kunden). Strenger? In `license.rs` den
  `Err(_)`-Zweig auf Sperren drehen.

---

## 11. Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| `tauri dev`: „external binary not found" | Den Platzhalter `apps/web/src-tauri/binaries/quant-os-api-aarch64-apple-darwin` nicht löschen, oder einmal Schritt 7 ausführen. |
| App startet, Desks zeigen „API not reachable" | Im schnellen Dev-Modus läuft das Backend nicht automatisch → manuell starten (Schritt 6-Hinweis), oder den Sidecar bauen (Schritt 7). |
| `desktop:build` bricht beim Codesign ab | Nicht-signierte Platzhalter-Binary gebündelt → erst Schritt 7 (echten Sidecar bauen). |
| PyInstaller-Fehler „module not found" | Fehlendes Paket in `requirements-api.txt` ergänzen + `--collect-submodules`/`--hidden-import` in `scripts/build_sidecar_mac.sh`. |
| Gatekeeper: „App kann nicht geöffnet werden" | Rechtsklick → **Öffnen** (für eigenen Test). Dauerhaft: Notarization. |
| Lizenz wird nicht akzeptiert | Im Lemon-Squeezy-Produkt „License keys" aktiviert? Schlüssel `active`? Internetverbindung? |

---

## 12. Befehls-Schnellreferenz

```bash
# ── Einmalige Einrichtung (Mac) ────────────────────────────────
xcode-select --install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup target add aarch64-apple-darwin
git clone <REPO_URL> Backtests && cd Backtests
python3 -m venv .venv && source .venv/bin/activate
pip install -r apps/api/requirements-api.txt
cd apps/web && npm install

# ── Gate testen (schnell) ──────────────────────────────────────
cd apps/web && npm run desktop:dev

# ── Autarke .dmg bauen ─────────────────────────────────────────
source .venv/bin/activate
.venv/bin/python scripts/build_registry.py # 0) Registry-DB (falls noch nicht da)
bash scripts/build_sidecar_mac.sh          # 1) Backend einfrieren
bash scripts/bundle_data.sh                # 2) Registry + Plots ins Bundle
cd apps/web
npm run tauri icon /pfad/logo.png          # 3) Icons (einmalig)
npm run desktop:build                      # 4) .app + .dmg
```

Fertig — die `.dmg` liegt unter
`apps/web/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/`.

---

## 13. Windows-Build (`.exe`-Installer)

Die App ist **cross-platform** — derselbe Code baut auf Windows einen nativen
NSIS-`.exe`-Installer. Den Windows-Build machst du **auf einem Windows-PC** (eine
`.exe`/MSI kann man nur unter Windows erzeugen, genau wie die `.dmg` nur auf dem Mac).

Tauri wählt das Bundle-Format automatisch nach Host-OS (`"targets": "all"` in
`tauri.conf.json`); die Windows-spezifischen Installer-Einstellungen (NSIS, WebView2-
Bootstrapper, Sprachen DE/EN) liegen in `apps/web/src-tauri/tauri.windows.conf.json`
und werden von Tauri v2 beim Windows-Build automatisch dazugemischt.

### 13.1 Einmalige Einrichtung (Windows)

```powershell
# (a) Rust über rustup (https://rustup.rs) — installiert das MSVC-Target automatisch.
#     Dazu die "Microsoft C++ Build Tools" (Visual Studio Installer → "Desktop development
#     with C++") — Tauri braucht den MSVC-Linker.
# (b) Node.js LTS (https://nodejs.org)
# (c) Edge WebView2 Runtime ist auf Windows 10/11 i.d.R. schon da; der Installer holt sie
#     sonst automatisch nach (downloadBootstrapper).

# Projekt holen + venv (im Repo-Wurzelordner):
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r apps/api/requirements-api.txt

cd apps\web
npm install
```

### 13.2 Gate testen (schnell, ohne kompletten Build)

```powershell
cd apps\web
npm run desktop:dev
```

Das Hard-Gate (7-Tage-Trial → EXPIRED → Lemon-Squeezy) funktioniert identisch zum Mac.
Der Vault liegt unter `%APPDATA%\com.quantos.pro\license.dat`. Für eine frische Trial:

```powershell
Remove-Item "$env:APPDATA\com.quantos.pro\license.dat"
```

### 13.3 Autarken `.exe`-Installer bauen

```powershell
# Repo-Wurzel, venv aktiv:
.\.venv\Scripts\python.exe scripts\build_registry.py   # 0) Registry-DB (falls noch nicht da)
powershell -ExecutionPolicy Bypass -File scripts\build_sidecar_win.ps1   # 1) Backend -> .exe einfrieren
powershell -ExecutionPolicy Bypass -File scripts\bundle_data.ps1         # 2) Registry + Plots ins Bundle
cd apps\web
npm run tauri icon C:\pfad\logo.png                    # 3) Icons (einmalig; erzeugt auch icon.ico)
npm run desktop:build:win                              # 4) NSIS-.exe-Installer
```

Ergebnis:

```
apps\web\src-tauri\target\x86_64-pc-windows-msvc\release\bundle\
└── nsis\Quant OS Pro_0.1.0_x64-setup.exe
```

> **MSI zusätzlich?** In `tauri.windows.conf.json` bei `bundle.targets` `"msi"` ergänzen
> (`["nsis", "msi"]`). Tauri lädt WiX automatisch nach. NSIS ist der empfohlene Default.
>
> **Code-Signing:** Ein nicht-signierter Installer zeigt eine SmartScreen-Warnung
> („Windows hat Ihren PC geschützt" → *Weitere Informationen* → *Trotzdem ausführen*).
> Für die Weitergabe ohne Warnung brauchst du ein **Authenticode-Code-Signing-Zertifikat**
> (OV/EV) — ein separater, späterer Schritt; in `tauri.windows.conf.json` unter
> `bundle.windows.signCommand`/`certificateThumbprint` konfigurierbar.

### 13.4 Windows-Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| `link.exe not found` / Linker-Fehler | MSVC Build Tools fehlen → Visual Studio Installer, „Desktop development with C++". |
| `external binary not found` | Den Platzhalter `binaries\quant-os-api-x86_64-pc-windows-msvc.exe` nicht löschen, oder Schritt 1 (Sidecar bauen). |
| App startet, Desks zeigen „API not reachable" | Im Dev-Modus läuft das Backend nicht automatisch → Backend manuell starten oder Sidecar bauen (Schritt 1). |
| PyInstaller „module not found" | Paket in `requirements-api.txt` ergänzen + `--collect-submodules`/`--hidden-import` in `scripts\build_sidecar_win.ps1`. |
| SmartScreen blockiert den Installer | Nicht-signiert → *Weitere Informationen* → *Trotzdem ausführen*. Dauerhaft: Authenticode-Zertifikat. |

> **Hinweis:** Wenn du keinen MSVC-Linker installieren willst, läuft `bundle_data.ps1` und
> `build_sidecar_win.ps1` auch ohne Rust — aber der finale `tauri build` braucht zwingend
> die MSVC Build Tools.
