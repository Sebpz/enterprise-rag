export default function TracesPage() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="rounded-xl border border-slate-700 bg-slate-800 px-8 py-10 text-center max-w-md">
        <h1 className="text-lg font-semibold text-white mb-2">Trace Explorer</h1>
        <p className="text-slate-400 text-sm">
          Coming soon. Traces are stored in Postgres{" "}
          <code className="font-mono text-sky-400">conversations</code> table.
        </p>
      </div>
    </div>
  );
}
