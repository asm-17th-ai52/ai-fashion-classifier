import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionState } from "@/store/sessionContext";
import { useSession } from "@/hooks/useSession";
import { useSimulation } from "@/hooks/useSimulation";
import ScoreGauge from "@/components/ScoreGauge";
import ChecklistSection from "@/components/ChecklistSection";
import SuggestionCard from "@/components/SuggestionCard";
import TopNav from "@/components/TopNav";
import SectionHead from "@/components/SectionHead";
import Pill from "@/components/Pill";
import type { Check } from "@/api/schemas";

const TIER_LABELS: Record<string, string> = {
  tier1_rag: "RAG 검색",
  tier2_live: "실시간 검색",
  fallback_general: "일반 가이드",
};

export default function ResultPage() {
  const state = useSessionState();
  const { reset } = useSession();
  const navigate = useNavigate();
  const { pending, activeSuggestionIds, toggle, clear } = useSimulation();

  useEffect(() => {
    if (state.status === "idle") navigate("/", { replace: true });
  }, [state.status, navigate]);

  if (state.status !== "success") return null;

  const { session, simulation } = state;
  const { recommendation, context } = session;
  const { score, checks, suggestions, blockers_failed } = recommendation;

  const checksById = new Map<string, Check>(checks.map((c) => [c.id, c]));
  const flippedToPass = new Set(simulation?.checks_flipped.to_pass ?? []);
  const displayScore = simulation?.simulated_overall ?? null;

  const blockerChecks = checks.filter(
    (c) => blockers_failed.includes(c.id) && c.result === "fail"
  );

  const sortedSuggestions = [
    ...suggestions.filter((s) => s.removes_blocker),
    ...suggestions.filter((s) => !s.removes_blocker),
  ];

  const dressTier = context.dress_code.tier;
  const passCount = checks.filter((c) => c.result === "pass" || flippedToPass.has(c.id)).length;
  const failCount = checks.filter((c) => c.result === "fail" && !flippedToPass.has(c.id)).length;
  const naCount = checks.filter((c) => !c.applicable).length;

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav
        step="result"
        rightSlot={
          <button
            onClick={() => { clear(); reset(); }}
            className="font-mono text-[10px] text-stone hover:text-ink transition-colors px-2.5 py-1 rounded border border-hairline2 hover:border-hairline-strong uppercase tracking-[0.1em]"
          >
            new analysis
          </button>
        }
      />

      {!context.weather.available && (
        <div role="status" className="bg-accent-yellow-soft border-b border-accent-yellow/20 px-4 py-1.5 text-[11px] text-accent-yellow text-center font-mono">
          날씨 데이터를 가져오지 못해 환경 점수에서 제외되었어요
        </div>
      )}

      <main className="max-w-7xl mx-auto px-4 py-6">

        {/* Top context strip */}
        <div className="flex flex-wrap gap-1.5 mb-4 animate-fade-in">
          {context.weather.available && typeof context.weather.temperature_celsius === "number" && (
            <Pill tone="blue">{Math.round(context.weather.temperature_celsius)}°c</Pill>
          )}
          <Pill tone="mute">tier · {TIER_LABELS[dressTier] ?? dressTier}</Pill>
          <Pill tone="green">pass {passCount}</Pill>
          <Pill tone="red">fail {failCount}</Pill>
          <Pill tone="mute">n/a {naCount}</Pill>
          {displayScore !== null && <Pill tone="blue">SIMULATION ACTIVE</Pill>}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr_1.1fr] gap-3">

          {/* Col 1: Score + blockers */}
          <div className="space-y-3">
            <div className="bg-panel border border-hairline2 rounded-xl p-4 animate-fade-in-up">
              <SectionHead idx="01" label="overall score" />
              <ScoreGauge
                score={score.overall}
                capApplied={score.cap_applied}
                simulatedScore={displayScore}
              />
            </div>

            {blockerChecks.length > 0 && (
              <div className="bg-panel border border-accent-red/30 rounded-xl p-4 animate-fade-in-up delay-100">
                <SectionHead idx="02" label="blockers" />
                <div className="space-y-2" role="alert">
                  {blockerChecks.map((c) => (
                    <div key={c.id} className="flex items-start gap-2 bg-accent-red-soft border border-accent-red/25 rounded-md px-3 py-2">
                      <span className="font-mono text-[10px] text-accent-red mt-0.5">{c.id}</span>
                      <span className="text-[12px] text-ink leading-snug">{c.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="bg-panel border border-hairline2 rounded-xl p-4 animate-fade-in-up delay-200">
              <SectionHead idx={blockerChecks.length > 0 ? "03" : "02"} label="group scores" />
              <div className="space-y-2 font-mono">
                {Object.entries(score.group_scores).map(([g, v]) => {
                  const pct = Math.round(v * 100);
                  return (
                    <div key={g} className="flex items-center gap-2">
                      <span className="text-[10px] text-stone uppercase w-20 tracking-[0.08em]">{g}</span>
                      <div className="flex-1 h-[3px] rounded-full bg-canvas overflow-hidden">
                        <div
                          className={`h-full ${pct >= 80 ? "bg-accent-green" : pct >= 60 ? "bg-accent-blue" : pct >= 40 ? "bg-accent-yellow" : "bg-accent-red"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-body w-7 text-right tabular-nums">{pct}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Col 2: Checks */}
          <div className="bg-panel border border-hairline2 rounded-xl p-4 animate-fade-in-up delay-100">
            <SectionHead idx={blockerChecks.length > 0 ? "04" : "03"} label="checklist · 17 items" />
            <ChecklistSection checks={checks} flippedToPass={flippedToPass} />
          </div>

          {/* Col 3: Suggestions */}
          <div className="space-y-3">
            <div className="animate-fade-in-up delay-200">
              <SectionHead
                idx={blockerChecks.length > 0 ? "05" : "04"}
                label="suggestions"
                action={
                  activeSuggestionIds.length > 0 ? (
                    <button
                      onClick={clear}
                      className="font-mono text-[9px] text-stone hover:text-ink uppercase tracking-[0.1em]"
                    >
                      reset sim
                    </button>
                  ) : undefined
                }
              />
              {sortedSuggestions.length > 0 ? (
                <div className="space-y-2">
                  {sortedSuggestions.map((s) => (
                    <SuggestionCard
                      key={s.id}
                      suggestion={s}
                      checksById={checksById}
                      isActive={activeSuggestionIds.includes(s.id)}
                      onToggle={() => toggle(s.id)}
                      simulationPending={pending}
                    />
                  ))}
                </div>
              ) : (
                <div className="bg-panel border border-hairline2 rounded-xl p-4 text-center font-mono text-[11px] text-stone">
                  no suggestions
                </div>
              )}
            </div>

            <button
              onClick={() => { clear(); reset(); }}
              className="w-full py-2.5 rounded-md bg-panelHi border border-hairline2 text-[11px] font-mono uppercase tracking-[0.1em] text-body hover:text-ink hover:border-hairline-strong transition-all"
            >
              ▸ new analysis
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
