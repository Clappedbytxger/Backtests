/** @type {import('next').NextConfig} */

// When building the Tauri desktop bundle (`TAURI=1 next build`, see `build:tauri`),
// emit a static export into `out/` that Tauri packages into the .app/.dmg. The normal
// `next build` / `next dev` workflow is unchanged (server features stay available).
const isTauri = process.env.TAURI === "1";

const nextConfig = isTauri
  ? {
      output: "export",
      // The desktop bundle is served from the file system / Tauri asset protocol,
      // so disable the image optimizer and use trailing-slash dir routing.
      images: { unoptimized: true },
      trailingSlash: true,
    }
  : {};

export default nextConfig;
