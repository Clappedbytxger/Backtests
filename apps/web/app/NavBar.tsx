"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMode } from "@/lib/mode";
import { useTour } from "@/lib/tour";

interface NavItem {
  href: string;
  label: string;
  dev?: boolean; // hidden in Simple mode (Phase 3.3 curated split)
}
interface NavGroup {
  label: string;
  accent: string; // tailwind text colour for the group
  items: NavItem[];
}

// Grouped navigation — keeps a growing surface readable instead of one long row.
// Simple mode keeps only the five decision surfaces (Swarm, Live, Seasonal, COT,
// Charts); everything else is Developer-only (`dev: true`).
const GROUPS: NavGroup[] = [
  {
    label: "Research",
    accent: "text-zinc-300",
    items: [
      { href: "/", label: "Strategies", dev: true },
      { href: "/ideas", label: "Research Hub", dev: true },
      { href: "/factory", label: "Alpha Factory", dev: true },
      { href: "/optimize", label: "Evolution Monitor", dev: true },
      { href: "/features", label: "Feature Store", dev: true },
      { href: "/agent", label: "Agent", dev: true },
      { href: "/academy", label: "Academy" },
    ],
  },
  {
    label: "Markets",
    accent: "text-amber-300",
    items: [
      { href: "/radar", label: "Weather Radar" },
      { href: "/cot", label: "COT Positioning" },
      { href: "/seasonal", label: "Seasonal" },
      { href: "/pairs", label: "Pairs / Cointegration", dev: true },
      { href: "/altdata", label: "Alternative Data", dev: true },
      { href: "/news", label: "News Terminal", dev: true },
    ],
  },
  {
    label: "Trading Desk",
    accent: "text-emerald-300",
    items: [
      { href: "/swarm", label: "Swarm Command Center" },
      { href: "/live", label: "Live Book" },
      { href: "/switchboard", label: "Switchboard", dev: true },
      { href: "/risk", label: "Risk Desk", dev: true },
      { href: "/attribution", label: "Attribution Desk", dev: true },
      { href: "/execution", label: "Execution Desk", dev: true },
      { href: "/charts", label: "Charts / Footprint" },
    ],
  },
];

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");

export default function NavBar() {
  const pathname = usePathname();
  const { isDev } = useMode();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));

  // filter items by mode, then drop any group left empty
  const groups = GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((i) => isDev || !i.dev),
  })).filter((g) => g.items.length > 0);

  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800 bg-zinc-950/85 backdrop-blur supports-[backdrop-filter]:bg-zinc-950/70">
      <nav className="mx-auto flex max-w-7xl items-center gap-1 px-6 py-3">
        <Link href="/swarm" className="mr-4 flex items-center gap-2 text-sm font-semibold tracking-tight">
          <span className="inline-block h-2 w-2 rounded-sm bg-emerald-400" />
          Quant-OS
        </Link>

        {groups.map((g) => {
          const groupActive = g.items.some((i) => isActive(i.href));
          return (
            <div key={g.label} className="group relative">
              <button
                className={cls(
                  "flex items-center gap-1 rounded-md px-3 py-1.5 text-sm transition-colors",
                  groupActive ? "bg-zinc-800/70 text-zinc-100" : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100",
                )}
              >
                {g.label}
                <svg className="h-3 w-3 opacity-50 transition-transform group-hover:rotate-180" viewBox="0 0 12 12" fill="none">
                  <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
                </svg>
              </button>
              {/* dropdown (hover-revealed; the pt-2 keeps the hover bridge intact) */}
              <div className="invisible absolute left-0 top-full z-50 pt-2 opacity-0 transition-all duration-150 group-hover:visible group-hover:opacity-100">
                <div className="min-w-[200px] overflow-hidden rounded-lg border border-zinc-800 bg-zinc-900/95 p-1 shadow-xl shadow-black/40 backdrop-blur">
                  <div className={cls("px-3 py-1 text-[10px] font-semibold uppercase tracking-widest", g.accent)}>
                    {g.label}
                  </div>
                  {g.items.map((i) => (
                    <Link
                      key={i.href}
                      href={i.href}
                      className={cls(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                        isActive(i.href)
                          ? "bg-zinc-800 text-zinc-100"
                          : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-100",
                      )}
                    >
                      <span
                        className={cls(
                          "h-1.5 w-1.5 rounded-full",
                          isActive(i.href) ? "bg-emerald-400" : "bg-zinc-700",
                        )}
                      />
                      {i.label}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          );
        })}

        <div className="ml-auto flex items-center gap-2">
          <ModeToggle />
          <TourButton />
          <Link
            href="/settings"
            aria-label="Settings"
            title="Einstellungen / API-Keys"
            className={cls(
              "rounded-md p-1.5 transition-colors",
              isActive("/settings")
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100",
            )}
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
              <path
                d="M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5z"
                stroke="currentColor"
                strokeWidth="1.4"
              />
              <path
                d="M10 2.5l1 2.2 2.4-.4.7 2.3 2.1 1.2-1 2.2 1 2.2-2.1 1.2-.7 2.3-2.4-.4-1 2.2-1-2.2-2.4.4-.7-2.3L2.8 12l1-2.2-1-2.2 2.1-1.2.7-2.3 2.4.4 1-2.2z"
                stroke="currentColor"
                strokeWidth="1.1"
                strokeLinejoin="round"
                opacity="0.55"
              />
            </svg>
          </Link>
        </div>
      </nav>
    </header>
  );
}

// Restart the onboarding tour ("60-Second AHA-Moment") from anywhere.
function TourButton() {
  const { start } = useTour();
  return (
    <button
      onClick={start}
      aria-label="Tour starten"
      title="Geführte Tour starten"
      className="flex h-7 w-7 items-center justify-center rounded-md text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-100"
    >
      <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.3" />
        <path
          d="M7.8 7.6a2.2 2.2 0 114.0 1.2c-.5.7-1.3 1-1.6 1.6-.15.3-.2.6-.2 1"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinecap="round"
        />
        <circle cx="10" cy="14.2" r="0.9" fill="currentColor" />
      </svg>
    </button>
  );
}

// segmented Simple / Developer toggle (the global UI mode switch)
function ModeToggle() {
  const { mode, setMode } = useMode();
  return (
    <div className="flex items-center rounded-md border border-zinc-800 bg-zinc-900/60 p-0.5 text-[11px]">
      {(["simple", "developer"] as const).map((m) => (
        <button
          key={m}
          onClick={() => setMode(m)}
          className={cls(
            "rounded px-2 py-1 font-medium capitalize transition-colors",
            mode === m ? "bg-zinc-700 text-zinc-100" : "text-zinc-500 hover:text-zinc-300",
          )}
          title={m === "simple" ? "Simple Mode — nur die Entscheidungs-Screens" : "Developer Mode — alle Werkzeuge"}
        >
          {m === "simple" ? "Simple" : "Dev"}
        </button>
      ))}
    </div>
  );
}
