"use client";

import katex from "katex";
import { Fragment, type ReactNode } from "react";
import { Viz } from "./viz";

/** Render a LaTeX string to KaTeX HTML; never throws on a bad formula. */
function tex(src: string, displayMode: boolean): ReactNode {
  const html = katex.renderToString(src, { displayMode, throwOnError: false, output: "html" });
  return <span dangerouslySetInnerHTML={{ __html: html }} />;
}

/** A paragraph that is just one $...$ formula (+ optional trailing punctuation). */
const DISPLAY_MATH = /^\$([^$]+)\$\s*([.,;:]?)$/;

/**
 * Minimal, dependency-free Markdown renderer for lesson bodies. It supports the
 * subset the curriculum uses (#/##/### headings, **bold**, `code`, - lists,
 * blockquotes, $inline math$) plus one custom directive:
 *
 *     ::viz NormalDistribution
 *
 * on its own line, which mounts the named interactive visualisation inline — the
 * core "prose, then interactive chart" didactic pattern.
 */
export default function Lesson({ markdown }: { markdown: string }) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  let para: string[] = [];
  let key = 0;

  const flushList = () => {
    if (list.length) {
      blocks.push(
        <ul key={key++} className="my-3 ml-5 list-disc space-y-1 text-zinc-300">
          {list.map((li, i) => (
            <li key={i}>{inline(li)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  const flushPara = () => {
    if (para.length) {
      const joined = para.join(" ").trim();
      const m = joined.match(DISPLAY_MATH);
      if (m) {
        // A standalone formula → centered display math (trailing punctuation dropped).
        blocks.push(
          <div key={key++} className="my-4 overflow-x-auto text-center text-zinc-100">
            {tex(m[1], true)}
          </div>,
        );
      } else {
        blocks.push(
          <p key={key++} className="my-3 leading-relaxed text-zinc-300">
            {inline(joined)}
          </p>,
        );
      }
      para = [];
    }
  };
  let quote: string[] = [];
  const flushQuote = () => {
    if (quote.length) {
      const buf = quote;
      blocks.push(
        <blockquote
          key={key++}
          className="my-4 border-l-2 border-blue-600 bg-blue-950/20 px-4 py-3 text-sm italic text-zinc-300"
        >
          {buf.map((q, i) => (
            <p key={i} className={i ? "mt-1" : ""}>{inline(q)}</p>
          ))}
        </blockquote>,
      );
      quote = [];
    }
  };
  const flush = () => {
    flushList();
    flushPara();
    flushQuote();
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.startsWith("::viz ")) {
      flush();
      blocks.push(
        <div key={key++} className="my-5">
          <Viz name={line.slice(6).trim()} />
        </div>,
      );
    } else if (line.startsWith("### ")) {
      flush();
      blocks.push(
        <h3 key={key++} className="mt-6 mb-2 text-base font-semibold text-zinc-100">
          {inline(line.slice(4))}
        </h3>,
      );
    } else if (line.startsWith("## ")) {
      flush();
      blocks.push(
        <h2 key={key++} className="mt-8 mb-3 text-xl font-semibold text-zinc-100">
          {inline(line.slice(3))}
        </h2>,
      );
    } else if (line.startsWith("# ")) {
      flush();
      blocks.push(
        <h1 key={key++} className="mt-2 mb-3 text-2xl font-semibold text-zinc-100">
          {inline(line.slice(2))}
        </h1>,
      );
    } else if (line.startsWith("> ")) {
      flushList();
      flushPara();
      quote.push(line.slice(2));
    } else if (/^[-*] /.test(line)) {
      flushPara();
      flushQuote();
      list.push(line.slice(2));
    } else if (line === "") {
      flush();
    } else if (list.length && /^\s/.test(raw)) {
      // Indented continuation of a soft-wrapped list item → append to it.
      list[list.length - 1] += " " + line.trim();
    } else {
      flushList();
      flushQuote();
      para.push(line);
    }
  }
  flush();

  return <div className="text-[15px]">{blocks}</div>;
}

/** Inline formatting: **bold**, `code`, $math$ (rendered monospace). */
function inline(text: string): ReactNode {
  const tokens = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\$[^$]+\$)/g);
  return tokens.map((t, i) => {
    if (t.startsWith("**") && t.endsWith("**"))
      return <strong key={i} className="font-semibold text-zinc-100">{t.slice(2, -2)}</strong>;
    if (t.startsWith("*") && t.endsWith("*") && t.length > 2)
      return <em key={i} className="italic text-zinc-200">{t.slice(1, -1)}</em>;
    if (t.startsWith("`") && t.endsWith("`"))
      return <code key={i} className="rounded bg-zinc-800 px-1 py-0.5 font-mono text-[13px] text-amber-300">{t.slice(1, -1)}</code>;
    if (t.startsWith("$") && t.endsWith("$") && t.length > 2)
      return <Fragment key={i}>{tex(t.slice(1, -1), false)}</Fragment>;
    return <Fragment key={i}>{t}</Fragment>;
  });
}
