import { promises as fs } from "fs";
import path from "path";
import AcademyModuleClient from "./AcademyModuleClient";

/**
 * Server wrapper for `output: 'export'` compatibility (Tauri desktop build). At build
 * time we pull the module ids out of `content/academy/curriculum.json` so the static
 * export emits one HTML shell per module; the shell hydrates the client component which
 * fetches the live module detail at runtime. Defensive: any read/parse failure falls
 * back to a single placeholder so the export build never breaks. (Academy is a
 * Developer-mode surface and not shown in the shipped Simple-mode app.)
 */
export async function generateStaticParams(): Promise<{ moduleId: string }[]> {
  try {
    const file = path.join(process.cwd(), "..", "..", "content", "academy", "curriculum.json");
    const raw = await fs.readFile(file, "utf-8");
    const data = JSON.parse(raw);
    const ids = new Set<string>();
    const walk = (o: unknown) => {
      if (!o || typeof o !== "object") return;
      const rec = o as Record<string, unknown>;
      if (typeof rec.id === "string") ids.add(rec.id);
      Object.values(rec).forEach(walk);
    };
    walk(data);
    const out = [...ids].map((moduleId) => ({ moduleId }));
    return out.length ? out : [{ moduleId: "intro" }];
  } catch {
    return [{ moduleId: "intro" }];
  }
}

export default function Page({ params }: { params: Promise<{ moduleId: string }> }) {
  return <AcademyModuleClient params={params} />;
}
