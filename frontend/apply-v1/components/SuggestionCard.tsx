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

function actionSummary(s: Suggestion): string {
  const { type, from, to, target_slot } = s.action;
  const slot = target_slot ?? "";
  if (type === "swap")    return `${slot ? slot + ": " : ""}${from} → ${to}`;
  if (type === "add")     return `${to} 추가`;
  if (type === "remove")  return `${from} 제거`;
  if (type === "recolor") return `${slot} 색상 → ${to}`;
  return "";
}

function actionType(s: Suggestion): string {
  return s.action.type.toUpperCase();
}

export default function SuggestionCard({
  suggestion, checksById, isActive, onToggle, simulationPending,
}: SuggestionCardProps) {
  const { removes_blocker, expected_overall_delta, fixes_check_ids, action } = suggestion;
  const isPositive = expected_overall_delta >= 0;

  return (
    <article
      className={`rounded-xl border p-3.5 space-y-2.5 transition-all ${
        removes_blocker
          ? "bg-accent-red-soft border-accent-red/30"
          : isActive
          ? "bg-accent-blue-soft border-accent-blue/30 shadow-glow-sm"
          : "bg-panel border-hairline2 hover:border-hairline-strong"
      }`}
    >
      {/* Header: ID + type + delta */}
      <div className="flex items-center gap-2">
        <span className="font-mono text-[10px] text-stone uppercase tracking-[0.1em]">
          {suggestion.id}
        </span>
        <Pill tone={action.type === "swap" ? "blue" : action.type === "add" ? "green" : "yellow"}>
          {actionType(suggestion)}
        </Pill>
        {removes_blocker && <Pill tone="red">blocker fix</Pill>}
        <div className="flex-1" />
        <span className={`font-mono text-base font-bold tabular-nums ${isPositive ? "text-accent-green" : "text-accent-red"}`}>
          {formatDelta(expected_overall_delta)}
        </span>
      </div>

      {/* User text */}
      <p className="text-[12.5px] text-ink leading-snug">
        {suggestion.user_facing_text ?? actionSummary(suggestion)}
      </p>

      {/* Before → After visual */}
      <div className="flex items-center gap-2 px-2.5 py-2 rounded-md bg-canvas border border-hairline">
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[8.5px] text-stone uppercase tracking-[0.1em] mb-0.5">
            {action.target_slot ?? "—"} · before
          </div>
          <div className="text-[11px] text-mute font-mono truncate">
            {action.from ?? "(없음)"}
          </div>
        </div>
        <svg className="w-3 h-3 text-accent-blue flex-shrink-0" viewBox="0 0 12 12" fill="none">
          <path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[8.5px] text-accent-blue uppercase tracking-[0.1em] mb-0.5">
            after
          </div>
          <div className="text-[11px] text-ink font-mono truncate">
            {action.to ?? "—"}
          </div>
        </div>
      </div>

      {/* Fixes which checks */}
      {fixes_check_ids.length > 0 && (
        <div className="flex flex-wrap items-center gap-1">
          <span className="font-mono text-[9px] text-stone uppercase tracking-[0.1em]">fixes</span>
          {fixes_check_ids.map((id) => {
            const check = checksById.get(id);
            return (
              <span
                key={id}
                title={check?.label ?? id}
                className="font-mono text-[9.5px] text-mute bg-panelHi border border-hairline2 rounded px-1.5 py-px"
              >
                {id}
              </span>
            );
          })}
        </div>
      )}

      {/* Rationale */}
      <ul className="space-y-0.5 pt-0.5">
        {suggestion.rationale_facts.map((fact, i) => (
          <li key={i} className="text-[10px] text-stone leading-relaxed font-mono">
            ▸ {fact}
          </li>
        ))}
      </ul>

      {/* Toggle */}
      <button
        onClick={onToggle}
        disabled={simulationPending}
        className={`w-full text-[11px] font-mono uppercase tracking-[0.1em] rounded-md py-2 font-semibold transition-all disabled:opacity-40 ${
          isActive
            ? "bg-accent-blue text-canvas hover:opacity-90"
            : "bg-panelHi text-body border border-hairline2 hover:border-hairline-strong hover:text-ink"
        }`}
        aria-pressed={isActive}
      >
        {isActive ? "✓ simulating" : "simulate"}
      </button>
    </article>
  );
}
