import { useState } from "react";
import type { Check, CheckGroup } from "@/api/schemas";
import Pill from "./Pill";

interface ChecklistSectionProps {
  checks: Check[];
  flippedToPass?: Set<string>;
}

const GROUP_ORDER: CheckGroup[] = ["dresscode", "consistency", "color", "confidence"];
const GROUP_SHORT: Record<CheckGroup, string> = {
  dresscode: "DRES", consistency: "CONS", color: "COLR", confidence: "CONF",
};

function MatrixCell({ check, flipped, onHover, hovered }: {
  check: Check; flipped: boolean; onHover: (id: string | null) => void; hovered: boolean;
}) {
  const result = flipped ? "pass" : check.result;
  const na = !check.applicable;
  const failBg   = "bg-accent-red-soft border-accent-red text-accent-red";
  const passBg   = "bg-accent-green border-accent-green text-[#001520]";
  const naBg     = "bg-hairline2 border-hairline2 text-stone";
  const cls = na ? naBg : result === "pass" ? passBg : failBg;
  return (
    <div
      onMouseEnter={() => onHover(check.id)}
      onMouseLeave={() => onHover(null)}
      title={check.label}
      className={`w-[22px] h-[22px] rounded-[3px] border grid place-items-center font-mono text-[8px] cursor-pointer transition-transform ${cls} ${hovered ? "scale-110" : ""} ${result === "pass" && check.applicable ? "shadow-[0_0_6px_#59d499]" : ""}`}
    >
      {check.id}
    </div>
  );
}

export default function ChecklistSection({ checks, flippedToPass = new Set() }: ChecklistSectionProps) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (id: string) => setExpanded((s) => {
    const next = new Set(s);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });

  return (
    <div className="space-y-6">
      {/* Matrix */}
      <div>
        <div className="font-mono text-[9px] text-stone mb-1.5 tracking-[0.1em]">MATRIX VIEW</div>
        <div className="flex gap-1">
          {GROUP_ORDER.map((g) => {
            const groupChecks = checks.filter((c) => c.group === g);
            return (
              <div key={g} className="flex-1 flex flex-col gap-[3px]">
                <div className="font-mono text-[9px] text-stone text-center mb-0.5">{GROUP_SHORT[g]}</div>
                <div className="flex gap-[3px] justify-center">
                  {groupChecks.map((c) => (
                    <MatrixCell
                      key={c.id}
                      check={c}
                      flipped={flippedToPass.has(c.id)}
                      onHover={setHovered}
                      hovered={hovered === c.id}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex gap-3 mt-3 font-mono text-[9px] text-stone">
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-accent-green" />pass</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-accent-red-soft border border-accent-red" />fail</span>
          <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-hairline2" />n/a</span>
        </div>
      </div>

      {/* Detail rows */}
      <div>
        <div className="font-mono text-[9px] text-stone mb-1.5 tracking-[0.1em]">DETAIL VIEW</div>
        <ul className="flex flex-col gap-1">
          {checks.map((c) => {
            const flipped = flippedToPass.has(c.id);
            const result = flipped ? "pass" : c.result;
            const na = !c.applicable;
            const isFail = result === "fail";
            const isOpen = expanded.has(c.id);
            const rowBg = isFail
              ? "bg-accent-red-soft/50 border-accent-red/15"
              : flipped
              ? "bg-accent-green-soft/50 border-accent-green/15"
              : "bg-transparent border-hairline";
            return (
              <li key={c.id} className={`rounded-md border ${rowBg}`}>
                <button
                  type="button"
                  className="w-full grid grid-cols-[30px_70px_1fr_auto_auto] gap-2.5 items-center px-2.5 py-2 text-left"
                  onClick={() => isFail && toggle(c.id)}
                  aria-expanded={isOpen}
                  disabled={!isFail}
                >
                  <span className="font-mono text-[10px] text-stone">{c.id}</span>
                  <span className={`font-mono text-[9px] uppercase tracking-[0.08em] ${na ? "text-stone" : isFail ? "text-accent-red" : "text-accent-green"}`}>
                    {na ? "n/a" : flipped ? "pass*" : result}
                  </span>
                  <span className={`text-[11px] ${na ? "text-stone line-through opacity-50" : "text-body"}`}>
                    {c.label}
                  </span>
                  {c.is_blocker && <Pill tone="red" className="!text-[8px]">blocker</Pill>}
                  {!c.is_blocker && <span />}
                  {isFail ? (
                    <svg className={`w-3 h-3 text-stone transition-transform ${isOpen ? "rotate-180" : ""}`} viewBox="0 0 12 12" fill="none">
                      <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : <span />}
                </button>
                {isOpen && c.evidence_facts.length > 0 && (
                  <ul className="mx-2.5 mb-2 mt-0 px-3 py-2 rounded-md bg-canvas border border-hairline space-y-1 animate-fade-in">
                    {c.evidence_facts.map((f, i) => (
                      <li key={i} className="text-[10px] text-mute leading-relaxed font-mono">· {f}</li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
