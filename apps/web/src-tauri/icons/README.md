# App-Icons

Tauri braucht für den `.dmg`/`.app`-Build die hier referenzierten Icon-Dateien
(`32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.icns`, `icon.ico`).

**Du musst sie nicht von Hand erstellen.** Lege ein einzelnes quadratisches PNG
(mind. 1024×1024, transparenter Hintergrund) an und lass Tauri den ganzen Satz
generieren — vom Ordner `apps/web/` aus:

```bash
npm run tauri icon /pfad/zu/deinem-logo.png
```

Das schreibt alle benötigten Größen (inkl. `icon.icns` für macOS) genau hierher.

> `tauri dev` läuft auch ohne fertige Icons (Tauri nutzt dann ein Default-Icon);
> der **Build** (`npm run desktop:build`) erwartet sie. Generiere sie also vor dem
> ersten `.dmg`-Build einmalig.
