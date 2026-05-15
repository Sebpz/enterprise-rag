"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { EvalRun } from "../../lib/types";

const METRICS = [
  { key: "faithfulness",      color: "#38bdf8", label: "Faithfulness" },
  { key: "answer_relevance",  color: "#a78bfa", label: "Answer Relevance" },
  { key: "context_precision", color: "#34d399", label: "Context Precision" },
  { key: "context_recall",    color: "#fb923c", label: "Context Recall" },
] as const;

interface ScoreChartProps {
  runs: EvalRun[];
}

export function ScoreChart({ runs }: ScoreChartProps) {
  const data = runs.map((r) => ({
    name: new Date(r.created_at).toLocaleDateString(),
    faithfulness: r.faithfulness,
    answer_relevance: r.answer_relevance,
    context_precision: r.context_precision,
    context_recall: r.context_recall,
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 4, right: 16, left: -16, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
        <YAxis domain={[0, 1]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
          labelStyle={{ color: "#e2e8f0" }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {METRICS.map(({ key, color, label }) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={color}
            name={label}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
