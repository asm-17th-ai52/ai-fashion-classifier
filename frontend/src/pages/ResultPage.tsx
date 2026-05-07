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
import type { Check } from "@/api/schemas";

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
  const { score, checks, suggestions } = recommendation;

  const checksById = new Map<string, Check>(checks.map((c) => [c.id, c]));
  const flippedToPass = new Set(simulation?.checks_flipped.to_pass ?? []);
  const displayScore = simulation?.simulated_overall ?? null;

  const sortedSuggestions = [
    ...suggestions.filter((s) => s.removes_blocker),
    ...suggestions.filter((s) => !s.removes_blocker),
  ];

  const dressTier = context.dress_code.tier;
  const passCount = checks.filter((c) => c.result === "pass" || flippedToPass.has(c.id)).length;
  const applicableCount = checks.filter((c) => c.applicable).length;

  return (
    <div className="min-h-screen bg-canvas text-body font-sans">
      <TopNav
        step="result"
        rightSlot={
          <button
            onClick={() => { clear(); reset(); }}
            className="font-mono text-[10px] text-stone hover:text-ink transition-colors px-2.5 py-1 rounded border border-hairline2 hover:border-hairline-strong uppercase tracking-[0.1em]"
          >
            new session
          </button>
        }
      />

      <div className="p-4 lg:p-6 grid grid-cols-1 lg:grid-cols-[320px_1fr_320px] gap-4">

        {/* ─── LEFT: Score + Group scores ─── */}
        <div className="flex flex-col gap-4">

          {/* 01 OVERALL FIT */}
          <div
            className="bg-panel border border-hairline rounded-xl p-5 relative overflow-hidden animate-fade-in"
          >
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background: `radial-gradient(ellipse 80% 60% at 50% 100%, ${
                  (displayScore ?? score.overall) >= 80
                    ? "rgba(110,231,167,0.12)"
                    : (displayScore ?? score.overall) >= 60
                    ? "rgba(95,184,255,0.10)"
                    : "rgba(251,191,87,0.10)"
                } 0%, transparent 70%)`,
              }}
            />
            <div className="relative">
              <SectionHead idx="01" label="OVERALL FIT" />
              <ScoreGauge
                score={score.overall}
                capApplied={score.cap_applied}
                simulatedScore={displayScore}
              />
            </div>
          </div>

          {/* 02 GROUP SCORES */}
          <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in">
            <SectionHead idx="02" label="GROUP SCORES" />
            <div className="flex flex-col gap-3.5">
              {Object.entries(score.group_scores).map(([g, v]) => {
                const pct = Math.round(v * 100);
                const color = pct >= 80 ? "#6ee7a7" : pct >= 60 ? "#5fb8ff" : pct >= 40 ? "#fbbf57" : "#ff6b6b";
                return (
                  <div key={g}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[11px] text-body">{g}</span>
                      <span
                        className="font-mono text-[11px] tabular-nums"
                        style={{ color }}
                      >
                        {pct.toString().padStart(3, " ")}
                      </span>
                    </div>
                    <div className="h-[4px] bg-hairline rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          background: color,
                          boxShadow: `0 0 4px ${color}`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* ─── CENTER: 17 Checks ─── */}
        <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in">
          <SectionHead
            idx="03"
            label="17 BINARY CHECKS"
            action={
              <span className="font-mono text-[10px] text-stone">
                pass {passCount} / applicable {applicableCount}
              </span>
            }
          />
          <ChecklistSection checks={checks} flippedToPass={flippedToPass} />
        </div>

        {/* ─── RIGHT: Context + Fix Actions ─── */}
        <div className="flex flex-col gap-4">

          {/* 04 CONTEXT */}
          <div className="bg-panel border border-hairline rounded-xl p-4 animate-fade-in">
            <SectionHead idx="04" label="CONTEXT" />
            <div className="font-mono text-[10px] leading-[1.7] text-body space-y-0.5">
              {context.weather.available && typeof context.weather.temperature_celsius === "number" && (
                <div>
                  🌡{" "}
                  {Math.round(context.weather.temperature_celsius)}°C
                  {typeof context.weather.feels_like_celsius === "number" && (
                    <span className="text-stone"> · 체감 {Math.round(context.weather.feels_like_celsius)}°C</span>
                  )}
                </div>
              )}
              {!context.weather.available && (
                <div className="text-stone">🌡 날씨 데이터 없음</div>
              )}
              <div className="mt-1" style={{ color: "#6ee7a7" }}>
                {dressTier}
                {session.meta.tier2_triggered && " · live search"}
              </div>
            </div>
          </div>

          {/* 05 FIX ACTIONS */}
          <div className="bg-panel border border-hairline rounded-xl p-4 animate-fade-in">
            <SectionHead
              idx="05"
              label="FIX ACTIONS"
              action={
                activeSuggestionIds.length > 0 ? (
                  <button
                    onClick={clear}
                    className="font-mono text-[9px] text-stone hover:text-ink uppercase tracking-[0.1em]"
                  >
                    reset
                  </button>
                ) : undefined
              }
            />
            {sortedSuggestions.length > 0 ? (
              <div className="flex flex-col gap-2.5">
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
              <div className="font-mono text-[11px] text-stone text-center py-4">
                no suggestions
              </div>
            )}
          </div>

          {/* New session */}
          <button
            onClick={() => { clear(); reset(); }}
            className="py-2.5 rounded-lg bg-panelHi border border-hairline2 text-[11px] font-mono uppercase tracking-[0.1em] text-body hover:text-ink hover:border-hairline-strong transition-all"
          >
            ← NEW SESSION
          </button>
        </div>
      </div>
    </div>
  );
}
