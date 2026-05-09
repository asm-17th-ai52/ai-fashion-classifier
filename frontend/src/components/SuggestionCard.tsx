import type { Suggestion, Check } from "@/api/schemas";
import { formatDelta } from "@/lib/format";
import Pill from "./Pill";

interface SuggestionCardProps {
  suggestion: Suggestion;
  checksById: Map<string, Check>;
  isActive: boolean;
  onToggle: () => void;
  simulationPending: boolean;
}

export default function SuggestionCard({
  suggestion, checksById, isActive, onToggle, simulationPending,
}: SuggestionCardProps) {
  const { removes_blocker, expected_overall_delta, fixes_check_ids, action } = suggestion;

  return (
    <article
      role="article"
      className={`rounded-xl border p-3 transition-all ${
        removes_blocker
          ? "bg-accent-red-soft border-accent-red/30"
          : isActive
          ? "bg-accent-blue-soft border-accent-blue"
          : "bg-panelHi border-hairline2 hover:border-hairline-strong"
      }`}
    >
      {/* Header: ID · type + blocker pill + delta */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[9px] text-stone tracking-[0.1em] uppercase">
            {suggestion.id} · {action.type.toUpperCase()}
          </span>
          {removes_blocker && <Pill tone="red">blocker fix</Pill>}
        </div>
        <span className="font-mono text-xs font-semibold text-accent-green tabular-nums">
          {formatDelta(expected_overall_delta)}
        </span>
      </div>

      {/* User text */}
      <p className="text-[11px] text-body leading-snug mb-2">
        {suggestion.user_facing_text}
      </p>

      {/* Before → After */}
      <div className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-canvas border border-hairline font-mono text-[10px] mb-2">
        {action.from && <span className="text-accent-red">{action.from}</span>}
        {action.from && <span className="text-stone">→</span>}
        <span className="text-accent-green">{action.to ?? "—"}</span>
      </div>

      {/* Fixes which checks */}
      {fixes_check_ids.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {fixes_check_ids.map((id) => {
            const check = checksById.get(id);
            return (
              <span
                key={id}
                title={check?.label ?? id}
                className="font-mono text-[9px] text-stone bg-canvas border border-hairline rounded px-1.5 py-px"
              >
                {id}
              </span>
            );
          })}
        </div>
      )}

      {/* Toggle button */}
      <button
        onClick={onToggle}
        disabled={simulationPending}
        aria-pressed={isActive}
        className={`w-full text-[9px] font-mono uppercase tracking-[0.1em] rounded py-1.5 font-semibold transition-all disabled:opacity-40 ${
          isActive
            ? "bg-accent-blue text-canvas hover:opacity-90"
            : "bg-canvas text-stone border border-hairline hover:text-ink"
        }`}
      >
        {isActive ? "✓ simulating" : "simulate"}
      </button>
    </article>
  );
}
