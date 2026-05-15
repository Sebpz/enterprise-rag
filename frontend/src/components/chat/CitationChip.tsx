"use client";

import { useState } from "react";
import type { Citation } from "../../hooks/useStreamingChat";

interface CitationChipProps {
  citation: Citation;
  index: number;
}

export function CitationChip({ citation, index }: CitationChipProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-900/50 border border-sky-700 text-sky-300 text-xs hover:bg-sky-800/60 transition-colors"
        title={citation.title}
      >
        [{index}] {citation.paper_id}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-end"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full sm:w-96 h-full sm:h-auto sm:max-h-[80vh] bg-slate-900 border-l border-slate-700 p-6 overflow-y-auto shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <h3 className="font-semibold text-white text-sm leading-tight pr-4">
                {citation.title}
              </h3>
              <button
                onClick={() => setOpen(false)}
                className="text-slate-400 hover:text-white text-lg leading-none flex-shrink-0"
              >
                ×
              </button>
            </div>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">Paper ID</dt>
                <dd className="font-mono text-sky-400">{citation.paper_id}</dd>
              </div>
              {citation.authors?.length > 0 && (
                <div>
                  <dt className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">Authors</dt>
                  <dd className="text-slate-300">{citation.authors.slice(0, 5).join(", ")}</dd>
                </div>
              )}
              {citation.relevance_score !== undefined && (
                <div>
                  <dt className="text-slate-400 text-xs uppercase tracking-wider mb-0.5">Relevance</dt>
                  <dd className="text-slate-300">{citation.relevance_score.toFixed(4)}</dd>
                </div>
              )}
            </dl>
            <a
              href={`https://arxiv.org/abs/${citation.paper_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block text-xs text-sky-400 underline hover:text-sky-300"
            >
              View on ArXiv →
            </a>
          </div>
        </div>
      )}
    </>
  );
}
