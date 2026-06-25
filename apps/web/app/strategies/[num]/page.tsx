import { promises as fs } from "fs";
import path from "path";
import StrategyClient from "./StrategyClient";

/**
 * Server wrapper so the dynamic route is compatible with `output: 'export'` (the Tauri
 * desktop build). At build time we enumerate the strategy folders (`NNNN_*`) under the
 * repo's `strategies/` dir so the static export emits one HTML shell per strategy. The
 * shell hydrates the client component, which fetches the real detail from the API at
 * runtime. New strategies require a rebuild to get a deep-link page (acceptable for a
 * shipped snapshot). In dev / non-export builds this enumeration is harmless.
 */
export async function generateStaticParams(): Promise<{ num: string }[]> {
  try {
    const dir = path.join(process.cwd(), "..", "..", "strategies");
    const entries = await fs.readdir(dir, { withFileTypes: true });
    const nums = entries
      .filter((e) => e.isDirectory() && /^\d{4}_/.test(e.name))
      .map((e) => ({ num: e.name.slice(0, 4) }));
    return nums.length ? nums : [{ num: "0001" }];
  } catch {
    // Repo layout not available at build time → emit a single placeholder shell.
    return [{ num: "0001" }];
  }
}

export default function Page() {
  return <StrategyClient />;
}
