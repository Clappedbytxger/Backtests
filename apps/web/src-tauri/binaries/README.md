# Sidecar binaries

This folder holds the **bundled Python API** that Tauri ships inside the `.app`/`.dmg`
(referenced by `externalBin` in `tauri.conf.json`).

- `quant-os-api-aarch64-apple-darwin` — the Apple-Silicon API binary. The file checked
  in here is a **text placeholder** so Tauri's `externalBin` existence check passes. It is
  **replaced** by the real binary when you run, on the Mac:

  ```bash
  bash scripts/build_sidecar_mac.sh
  ```

The real binary is large (hundreds of MB). **Do not commit it.** After building, either
leave it untracked or tell git to ignore the local change:

```bash
git update-index --assume-unchanged "apps/web/src-tauri/binaries/quant-os-api-aarch64-apple-darwin"
```

> The naming suffix `-aarch64-apple-darwin` is mandatory — Tauri resolves the sidecar for
> the build target by that exact triple. For an Intel build it would be
> `-x86_64-apple-darwin`; for a universal binary, both.
