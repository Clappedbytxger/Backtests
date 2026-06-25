# Bundled app resources

Tauri ships everything in this folder inside the `.app`/`.dmg` (under `Contents/Resources/`,
declared by `bundle.resources` in `tauri.conf.json`). At runtime the Rust layer passes the
path here to the Python sidecar as `QOS_BUNDLE_DIR`, which seeds it into a writable data
directory on first launch — so the shipped app starts **self-contained with data**.

**This folder is populated automatically — do not fill it by hand.** Before building the
`.dmg`, run from the repo root:

```bash
bash scripts/bundle_data.sh
```

That copies:

- `strategies.db` — the strategy registry (dashboard table + detail pages)
- `strategies/<NNNN_…>/results/*.png` — the plots on each strategy detail page

The copied data (`strategies.db`, `strategies/`) is git-ignored here (~16 MB) — only this
README is tracked. If `strategies.db` is missing, build it first with
`.venv/bin/python scripts/build_registry.py`.
