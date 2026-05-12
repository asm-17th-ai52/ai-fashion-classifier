type Step = "upload" | "analyzing" | "result";

const STEPS: { id: Step; label: string }[] = [
  { id: "upload",    label: "INPUT" },
  { id: "analyzing", label: "ANALYZE" },
  { id: "result",    label: "REPORT" },
];

interface TopNavProps {
  step: Step;
  rightSlot?: React.ReactNode;
}

export default function TopNav({ step, rightSlot }: TopNavProps) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <nav className="flex items-center h-12 px-6 border-b border-hairline bg-canvas">
      {/* Logo */}
      <div className="flex items-center gap-2.5">
        <div className="w-[22px] h-[22px] rounded-[5px] border border-hairline2 bg-panelHi grid place-items-center">
          <div className="w-1.5 h-1.5 rounded-full bg-accent-blue shadow-glow-sm" style={{ boxShadow: "0 0 8px #57c1ff" }} />
        </div>
        <span className="text-xs font-semibold text-ink tracking-tight">fashion.ai</span>
        <span className="text-[10px] text-stone font-mono ml-1">/v1.0</span>
      </div>

      {/* Steps */}
      <div className="flex items-center gap-1 ml-8">
        {STEPS.map((s, i) => {
          const active = s.id === step;
          const done = STEPS.findIndex((x) => x.id === step) > i;
          const tone = active ? "text-accent-blue" : done ? "text-body" : "text-stone";
          return (
            <div key={s.id} className="flex items-center gap-1">
              <span className={`font-mono text-[10px] tracking-[0.1em] ${tone}`}>
                {String(i + 1).padStart(2, "0")} {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <span className="text-stone mx-1.5 font-mono text-[10px]">›</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex-1" />

      {rightSlot ?? (
        <span className="font-mono text-[10px] text-stone">
          sess_{Math.random().toString(36).slice(2, 5)} · {today}
        </span>
      )}
    </nav>
  );
}
