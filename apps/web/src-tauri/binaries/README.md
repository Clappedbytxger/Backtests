# Sidecar binaries

This folder holds the **bundled Python API** that Tauri ships inside the `.app`/`.dmg`
(referenced by `externalBin` in `tauri.conf.json`).

- `quant-os-api-aarch64-apple-darwin` — the Apple-Silicon API binary. The file checked
  in here is a **text placeholder** so Tauri's `externalBin` existence check passes. It is
  **replaced** by the real binary when you run, on the Mac:

  ```bash
  bash scripts/build_sidecar_mac.sh
  ```

- `quant-os-api-x86_64-pc-windows-msvc.exe` — the Windows (x64) API binary, also a
  **text placeholder**. Replace it by running, on Windows (inside the venv):

  ```powershell
  powershell -ExecutionPolicy Bypass -File scripts\build_sidecar_win.ps1
  ```

The real binaries are large (hundreds of MB). **Do not commit them.** After building, either
leave them untracked or tell git to ignore the local change:

```bash
git update-index --assume-unchanged "apps/web/src-tauri/binaries/quant-os-api-aarch64-apple-darwin"
git update-index --assume-unchanged "apps/web/src-tauri/binaries/quant-os-api-x86_64-pc-windows-msvc.exe"
```

> The naming suffix (`-aarch64-apple-darwin`, `-x86_64-pc-windows-msvc`) is mandatory —
> Tauri resolves the sidecar for the build target by that exact triple (Windows also needs
> the `.exe` extension). For an Intel Mac it would be `-x86_64-apple-darwin`; for a
> universal macOS binary, both Mac triples.
