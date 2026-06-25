"use client";

/**
 * Dynamic correlation matrix of the book's daily returns. Diverging colour:
 * strong POSITIVE correlation (> 0.6 = hidden concentration risk) burns dark red,
 * uncorrelated pairs sit in cool slate, negative (genuine hedges) shade blue.
 * Hover shows the exact value; clicking a cell drills into the rolling correlation.
 */
export default function RiskHeatmap({
  labels,
  matrix,
  onSelect,
  selected,
}: {
  labels: string[];
  matrix: (number | null)[][];
  onSelect?: (a: string, b: string) => void;
  selected?: { a: string; b: string } | null;
}) {
  const n = labels.length;
  const short = (l: string) => l.slice(0, 4);

  // diverging: 0 → slate(39,39,42); +1 → red(220,38,38); −1 → blue(59,130,246).
  const color = (c: number | null): string => {
    if (c == null) return "#0a0a0a";
    const base = [39, 39, 42];
    if (c >= 0) {
      const e = c < 0.6 ? c * 0.7 : 0.42 + (c - 0.6) * 1.45; // emphasise the danger zone
      const t = Math.min(e, 1);
      const tgt = [220, 38, 38];
      return `rgb(${base.map((b, i) => Math.round(b + (tgt[i] - b) * t)).join(",")})`;
    }
    const t = Math.min(-c, 1);
    const tgt = [59, 130, 246];
    return `rgb(${base.map((b, i) => Math.round(b + (tgt[i] - b) * t)).join(",")})`;
  };

  const isSel = (i: number, j: number) =>
    selected != null &&
    ((short(labels[i]) === selected.a && short(labels[j]) === selected.b) ||
      (short(labels[i]) === selected.b && short(labels[j]) === selected.a));

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th className="sticky left-0 bg-zinc-950" />
            {labels.map((t) => (
              <th key={t} className="px-1 pb-1 text-[9px] font-mono font-normal text-zinc-500" title={t}>
                {short(t)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((rowL, i) => (
            <tr key={rowL}>
              <td
                className="sticky left-0 z-10 bg-zinc-950 pr-2 text-right text-[10px] font-mono text-zinc-400"
                title={rowL}
              >
                {short(rowL)}
              </td>
              {labels.map((colL, j) => {
                const c = matrix[i]?.[j] ?? null;
                const hot = c != null && i !== j && c > 0.6;
                return (
                  <td key={colL} className="p-0">
                    <button
                      disabled={i === j}
                      onClick={() => onSelect?.(short(rowL), short(colL))}
                      title={
                        i === j
                          ? rowL
                          : `${rowL}\n× ${colL}\nρ = ${c == null ? "n/a" : c.toFixed(3)}`
                      }
                      className="h-7 w-7 rounded-sm text-[8px] font-semibold transition hover:outline hover:outline-1 hover:outline-zinc-200 disabled:cursor-default"
                      style={{
                        background: i === j ? "#18181b" : color(c),
                        outline: isSel(i, j)
                          ? "2px solid #fafafa"
                          : hot
                            ? "1.5px solid #fca5a5"
                            : "none",
                        color: hot ? "#fee2e2" : "rgba(255,255,255,0.55)",
                      }}
                    >
                      {i === j ? "" : c == null ? "·" : c.toFixed(1).replace("0.", ".")}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-zinc-500">
        <span>−1 hedge</span>
        <div
          className="h-2.5 w-48 rounded-full"
          style={{
            background:
              "linear-gradient(90deg, rgb(59,130,246), rgb(39,39,42) 50%, rgb(220,38,38))",
          }}
        />
        <span>+1 gleichläufig</span>
        <span className="ml-2 rounded px-1 text-red-200 outline outline-1 outline-red-400">
          ρ &gt; 0.6 = verstecktes Klumpenrisiko
        </span>
      </div>
    </div>
  );
}
