const ITEMS = [
  { label: "pending", color: "bg-slate-500/40" },
  { label: "running", color: "bg-blue-500/70" },
  { label: "completed", color: "bg-emerald-500/70" },
  { label: "failed", color: "bg-red-500/70" },
  { label: "skipped", color: "border border-dashed border-slate-500/50 bg-transparent" },
] as const;

export function PipelineLegend() {
  return (
    <div className="flex items-center justify-center gap-4 border-b border-white/[0.05] px-4 py-2 text-[10px] text-slate-400">
      {ITEMS.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <span className={`inline-block h-2 w-2 rounded-sm ${item.color}`} />
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
