"use client";

import { Fragment, type ReactNode } from "react";

/** Inline: **bold** and `code`. */
function inline(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((t, i) => {
    if (t.startsWith("**") && t.endsWith("**"))
      return <strong key={i} className="font-semibold text-zinc-100">{t.slice(2, -2)}</strong>;
    if (t.startsWith("`") && t.endsWith("`"))
      return <code key={i} className="rounded bg-zinc-800 px-1 py-0.5 font-mono text-[12px] text-amber-300">{t.slice(1, -1)}</code>;
    return <Fragment key={i}>{t}</Fragment>;
  });
}

/**
 * Minimal Markdown renderer for Alpha Factory reports — handles the subset the report
 * template uses: #/##/### headings, GitHub tables, ``` code fences, blockquotes, **bold**,
 * `code`, and the <details> signal block. No dependency, tables included.
 */
export default function ReportMarkdown({ markdown }: { markdown: string }) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  let key = 0;
  let para: string[] = [];

  const flushPara = () => {
    if (para.length) {
      blocks.push(
        <p key={key++} className="my-2 leading-relaxed text-zinc-300">{inline(para.join(" "))}</p>,
      );
      para = [];
    }
  };

  while (i < lines.length) {
    const line = lines[i];

    // code fence
    if (line.trimStart().startsWith("```")) {
      flushPara();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) buf.push(lines[i++]);
      i++; // closing fence
      blocks.push(
        <pre key={key++} className="my-3 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-[12px] text-zinc-300">
          {buf.join("\n")}
        </pre>,
      );
      continue;
    }

    // table: a header row containing | followed by a |---| separator
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      flushPara();
      const cells = (s: string) => s.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|").map((c) => c.trim());
      const header = cells(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes("|")) rows.push(cells(lines[i++]));
      blocks.push(
        <div key={key++} className="my-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-zinc-400">
              <tr className="border-b border-zinc-700">
                {header.map((h, j) => <th key={j} className="py-1.5 pr-4 font-medium">{inline(h)}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr key={ri} className="border-b border-zinc-900">
                  {r.map((c, ci) => <td key={ci} className="py-1.5 pr-4 text-zinc-300">{inline(c)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (line.startsWith("### ")) { flushPara(); blocks.push(<h3 key={key++} className="mt-5 mb-2 text-base font-semibold text-zinc-100">{inline(line.slice(4))}</h3>); i++; continue; }
    if (line.startsWith("## ")) { flushPara(); blocks.push(<h2 key={key++} className="mt-6 mb-2 text-xl font-semibold text-zinc-100">{inline(line.slice(3))}</h2>); i++; continue; }
    if (line.startsWith("# ")) { flushPara(); blocks.push(<h1 key={key++} className="mt-4 mb-2 text-2xl font-semibold text-zinc-100">{inline(line.slice(2))}</h1>); i++; continue; }
    if (line.startsWith("> ")) { flushPara(); blocks.push(<blockquote key={key++} className="my-3 border-l-2 border-blue-600 bg-blue-950/20 px-3 py-2 text-sm italic text-zinc-400">{inline(line.slice(2))}</blockquote>); i++; continue; }
    if (line.trim() === "---") { flushPara(); blocks.push(<hr key={key++} className="my-4 border-zinc-800" />); i++; continue; }
    if (/^<\/?(details|summary)/.test(line.trim())) {
      // signal-code <details> wrapper: render <summary> text as a label, skip the tags
      const m = line.match(/<summary>(.*?)<\/summary>/);
      if (m) { flushPara(); blocks.push(<div key={key++} className="mt-4 mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">{m[1]}</div>); }
      i++; continue;
    }
    if (line.trim() === "") { flushPara(); i++; continue; }
    para.push(line);
    i++;
  }
  flushPara();
  return <div className="text-[15px]">{blocks}</div>;
}
