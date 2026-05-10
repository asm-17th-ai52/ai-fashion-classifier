import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionState } from "@/store/sessionContext";
import { useSession } from "@/hooks/useSession";
import { useSimulation } from "@/hooks/useSimulation";
import ScoreGauge from "@/components/ScoreGauge";
import ChecklistSection from "@/components/ChecklistSection";
import SuggestionCard from "@/components/SuggestionCard";
import TopNav from "@/components/TopNav";
import type { Check } from "@/api/schemas";
import { GROUP_LABELS } from "@/lib/i18n";

export default function ResultPage() {
  const state = useSessionState();
  const { reset } = useSession();
  const navigate = useNavigate();
  const { pending, activeSuggestionIds, toggle, clear } = useSimulation();
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    if (state.status === "idle") navigate("/", { replace: true });
  }, [state.status, navigate]);

  if (state.status !== "success") return null;

  const { session, simulation } = state;
  const { recommendation, context } = session;
  const { score, checks, suggestions, explanation } = recommendation;

  const checksById = new Map<string, Check>(checks.map((c) => [c.id, c]));
  const flippedToPass = new Set(simulation?.checks_flipped.to_pass ?? []);
  const displayScore = simulation?.simulated_overall ?? null;

  const sortedSuggestions = [
    ...suggestions.filter((s) => s.removes_blocker),
    ...suggestions.filter((s) => !s.removes_blocker),
  ];

  const failedChecks = checks.filter(
    (c) => c.applicable && !flippedToPass.has(c.id) && c.result === "fail"
  );

  const dressTier = context.dress_code.tier;
  const tierLabel: Record<string, string> = {
    tier1: "RAG 기반 분석",
    tier2_live: "실시간 외부 자료 기반",
    fallback_general: "일반 가이드 적용",
  };

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

      {/* ── 3-column grid ── */}
      <div className="p-4 lg:p-6 grid grid-cols-1 lg:grid-cols-[260px_1fr_280px] gap-4 items-start">

        {/* ──────────── LEFT: Score + Groups ──────────── */}
        <div className="flex flex-col gap-4">

          {/* 01 OVERALL FIT */}
          <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in relative overflow-hidden">
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
              <div className="font-mono text-[9px] text-stone tracking-[0.1em] uppercase mb-3">
                01 · Overall Fit
              </div>
              <ScoreGauge
                score={score.overall}
                capApplied={score.cap_applied}
                simulatedScore={displayScore}
              />
              <div className="mt-3 flex flex-wrap gap-1.5">
                {score.cap_applied === "blocker_cap_50" && (
                  <span className="inline-flex items-center gap-1 font-mono text-[8px] bg-accent-red-soft border border-accent-red/40 text-accent-red rounded-full px-2 py-0.5">
                    ⚠ 핵심 미스
                  </span>
                )}
                <span className="font-mono text-[8px] text-stone border border-hairline rounded-full px-2 py-0.5">
                  {tierLabel[dressTier] ?? dressTier}
                </span>
              </div>
            </div>
          </div>

          {/* 02 GROUP SCORES */}
          <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in">
            <div className="font-mono text-[9px] text-stone tracking-[0.1em] uppercase mb-3">
              02 · Group Scores
            </div>
            <div className="flex flex-col gap-3">
              {Object.entries(score.group_scores).map(([g, v]) => {
                const pct = Math.round(v * 100);
                const color =
                  pct >= 80 ? "#6ee7a7" :
                  pct >= 60 ? "#5fb8ff" :
                  pct >= 40 ? "#fbbf57" : "#ff6b6b";
                return (
                  <div key={g}>
                    <div className="flex justify-between mb-1">
                      <span className="text-[11px] text-body">
                        {GROUP_LABELS[g as keyof typeof GROUP_LABELS] ?? g}
                      </span>
                      <span className="font-mono text-[11px] tabular-nums" style={{ color }}>
                        {pct}
                      </span>
                    </div>
                    <div className="h-[3px] bg-hairline rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${pct}%`, background: color, boxShadow: `0 0 4px ${color}` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* New session */}
          <button
            onClick={() => { clear(); reset(); }}
            className="py-2.5 rounded-xl bg-panelHi border border-hairline2 text-[10px] font-mono uppercase tracking-[0.1em] text-body hover:text-ink hover:border-hairline-strong transition-all"
          >
            ← 새 분석 시작
          </button>
        </div>

        {/* ──────────── CENTER: AI 평가 + 문제점 ──────────── */}
        <div className="flex flex-col gap-4">

          {/* 03 AI 종합 평가 */}
          <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-5 h-5 rounded-full bg-accent-blue/15 border border-accent-blue/30 grid place-items-center flex-shrink-0">
                <span className="font-mono text-[8px] text-accent-blue">AI</span>
              </div>
              <span className="font-mono text-[9px] text-stone tracking-[0.08em] uppercase">
                03 · 종합 평가
              </span>
            </div>
            <p className="text-[13px] text-body leading-[1.8] whitespace-pre-wrap">
              {explanation || "분석 결과를 불러오는 중입니다."}
            </p>
          </div>

          {/* 04 발견된 문제점 */}
          {failedChecks.length > 0 ? (
            <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in">
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-[9px] text-stone tracking-[0.08em] uppercase">
                  04 · 발견된 문제점
                </span>
                <span className="font-mono text-[9px] text-accent-red">{failedChecks.length}건</span>
              </div>
              <ul className="space-y-3.5">
                {failedChecks.map((c) => (
                  <li key={c.id} className="flex items-start gap-2.5">
                    <span className="mt-0.5 w-4 h-4 rounded-full bg-accent-red-soft border border-accent-red/40 grid place-items-center flex-shrink-0">
                      <span className="text-[7px] text-accent-red font-bold">✗</span>
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-[12px] text-body font-medium leading-snug">
                          {c.label}
                        </span>
                        {c.is_blocker && (
                          <span className="font-mono text-[8px] bg-accent-red-soft border border-accent-red/40 text-accent-red rounded px-1.5 py-px uppercase flex-shrink-0">
                            blocker
                          </span>
                        )}
                      </div>
                      {c.evidence_facts.length > 0 && (
                        <ul className="mt-1 space-y-0.5">
                          {c.evidence_facts.map((f, i) => (
                            <li key={i} className="text-[11px] text-mute leading-relaxed">
                              · {f}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in">
              <div className="flex items-center gap-2">
                <span className="w-4 h-4 rounded-full bg-accent-green/20 border border-accent-green/40 grid place-items-center flex-shrink-0">
                  <span className="text-[7px] text-accent-green font-bold">✓</span>
                </span>
                <span className="text-[12px] text-body">모든 적용 체크를 통과했습니다.</span>
              </div>
            </div>
          )}

          {/* 05 상세 분석 (접기/펼치기) */}
          <div className="bg-panel border border-hairline rounded-xl overflow-hidden animate-fade-in">
            <button
              className="w-full flex items-center justify-between px-5 py-3.5 hover:bg-panelHi transition-colors"
              onClick={() => setDetailOpen((v) => !v)}
              aria-expanded={detailOpen}
            >
              <span className="font-mono text-[9px] text-stone tracking-[0.08em] uppercase">
                05 · 상세 체크 목록
              </span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[9px] text-stone">
                  {checks.filter((c) => c.result === "pass" || flippedToPass.has(c.id)).length}
                  {" / "}
                  {checks.filter((c) => c.applicable).length} pass
                </span>
                <svg
                  className={`w-3.5 h-3.5 text-stone transition-transform ${detailOpen ? "rotate-180" : ""}`}
                  viewBox="0 0 12 12" fill="none"
                >
                  <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            </button>
            {detailOpen && (
              <div className="px-5 pb-5 border-t border-hairline animate-fade-in">
                <div className="mt-4">
                  <ChecklistSection checks={checks} flippedToPass={flippedToPass} />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ──────────── RIGHT: 개선 제안 ──────────── */}
        <div className="flex flex-col gap-4">
          <div className="bg-panel border border-hairline rounded-xl p-5 animate-fade-in">
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-[9px] text-stone tracking-[0.08em] uppercase">
                06 · 개선 제안
              </span>
              {activeSuggestionIds.length > 0 && (
                <button
                  onClick={clear}
                  className="font-mono text-[9px] text-stone hover:text-ink uppercase tracking-[0.1em]"
                >
                  reset
                </button>
              )}
            </div>
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
              <p className="font-mono text-[11px] text-stone text-center py-6">
                no suggestions
              </p>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
