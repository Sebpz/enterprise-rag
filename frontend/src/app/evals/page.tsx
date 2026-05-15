"use client";

import { useEvalScores } from "../../hooks/useEvalScores";
import { ScoreChart } from "../../components/evals/ScoreChart";

const METRICS = [
  { key: "faithfulness",      label: "Faithfulness"      },
  { key: "answer_relevance",  label: "Answer Relevance"  },
  { key: "context_precision", label: "Context Precision" },
  { key: "context_recall",    label: "Context Recall"    },
] as const;

export default function EvalsPage() {
  const { data: runs, isLoading, error } = useEvalScores();

  return (
    <div className="h-full overflow-y-auto px-6 py-6">
      <h1 className="text-xl font-semibold text-white mb-6">Evaluation Dashboard</h1>

      {isLoading && (
        <div className="text-slate-400 text-sm">Loading eval results…</div>
      )}

      {error && (
        <div className="rounded-xl border border-slate-700 bg-slate-800 px-4 py-6 text-center text-slate-400 text-sm">
          No eval data available. Run{" "}
          <code className="font-mono text-sky-400">python -m evals.run_evals</code> to generate.
        </div>
      )}

      {runs && runs.length > 0 && (
        <>
          {/* Latest run summary cards */}
          {(() => {
            const latest = runs[runs.length - 1];
            return (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
                {METRICS.map(({ key, label }) => (
                  <div
                    key={key}
                    className="rounded-xl bg-slate-800 border border-slate-700 px-4 py-3"
                  >
                    <p className="text-xs text-slate-400 mb-1">{label}</p>
                    <p className="text-2xl font-mono font-semibold text-white">
                      {(latest[key] as number).toFixed(3)}
                    </p>
                  </div>
                ))}
              </div>
            );
          })()}

          {/* Trend chart */}
          <div className="rounded-xl bg-slate-800 border border-slate-700 px-4 py-4 mb-6">
            <h2 className="text-sm font-medium text-slate-300 mb-4">Metric Trends</h2>
            <ScoreChart runs={runs} />
          </div>

          {/* Runs table */}
          <div className="rounded-xl bg-slate-800 border border-slate-700 overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 uppercase tracking-wider">
                  <th className="px-4 py-3 text-left">Version</th>
                  <th className="px-4 py-3 text-right">Faithfulness</th>
                  <th className="px-4 py-3 text-right">Relevance</th>
                  <th className="px-4 py-3 text-right">Precision</th>
                  <th className="px-4 py-3 text-right">Recall</th>
                  <th className="px-4 py-3 text-right">Qs</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-right">Date</th>
                </tr>
              </thead>
              <tbody>
                {[...runs].reverse().map((r) => (
                  <tr key={r.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-2.5 font-mono text-sky-400">{r.config_version}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{r.faithfulness.toFixed(3)}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{r.answer_relevance.toFixed(3)}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{r.context_precision.toFixed(3)}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{r.context_recall.toFixed(3)}</td>
                    <td className="px-4 py-2.5 text-right text-slate-300">{r.questions_tested}</td>
                    <td className="px-4 py-2.5 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          r.passed_regression
                            ? "bg-green-900/50 text-green-400 border border-green-700"
                            : "bg-red-900/50 text-red-400 border border-red-700"
                        }`}
                      >
                        {r.passed_regression ? "PASS" : "FAIL"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right text-slate-400">
                      {new Date(r.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
