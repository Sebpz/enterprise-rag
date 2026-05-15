"use client";

import { useState } from "react";
import type { AgentStep } from "../../hooks/useStreamingChat";

interface AgentStepsProps {
  steps: AgentStep[];
}

export function AgentSteps({ steps }: AgentStepsProps) {
  const [open, setOpen] = useState(false);

  if (steps.length === 0) return null;

  return (
    <div className="mb-2 text-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-slate-400 hover:text-slate-200 text-xs underline"
      >
        {open ? "Hide" : "Show"} agent steps ({steps.length})
      </button>
      {open && (
        <ol className="mt-2 space-y-2 pl-3 border-l border-slate-600">
          {steps.map((step, i) => (
            <li key={i}>
              <span className="font-mono text-xs text-sky-400">[{step.node}]</span>{" "}
              <span className="text-slate-300 text-xs">{step.output.slice(0, 200)}</span>
              {step.tool_call && (
                <div className="text-xs text-slate-500 mt-0.5">
                  Tool: {step.tool_call.tool} — {step.tool_call.query}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
