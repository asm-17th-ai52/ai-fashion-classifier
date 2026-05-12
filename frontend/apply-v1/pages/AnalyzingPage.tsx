import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionState } from "@/store/sessionContext";
import { useSession } from "@/hooks/useSession";
import TopNav from "@/components/TopNav";
import Pill from "@/components/Pill";

const ERROR_MESSAGES: Record<string, string> = {
  person_not_detected: "사람이 정면으로 보이는 사진을 사용해 주세요.",
  image_too_large: "10MB 이하 이미지만 사용 가능합니다.",
  image_invalid: "이미지를 읽을 수 없습니다. 다른 파일을 시도해 주세요.",
  rate_limited: "잠시 후 다시 시도해 주세요.",
  agent_failed: "AI 분석에 실패했어요. 다시 시도해 주세요.",
};

interface Stage {
  id: string;
  agent: string;
  label: string;
  startAt: number;
  doneAt: number;
  logs: string[];
}

function buildStages(isCustom: boolean): Stage[] {
  return [
    {
      id: "vision", agent: "VISION", label: "착장 이미지 분석",
      startAt: 0, doneAt: 0.3,
      logs: [
        "▸ loading model: clip-vit-large-patch14",
        "▸ detecting person bbox… ok (conf 0.94)",
        "▸ segment garments… 3 found",
        "▸ extract: top=드레스셔츠 bottom=치노 shoes=로퍼",
        "▸ formality scores: [85, 45, 20]",
      ],
    },
    {
      id: "context", agent: "CONTEXT",
      label: isCustom ? "실시간 외부 자료 검색 포함" : "날씨 · 드레스코드 데이터 조회",
      startAt: 0.3, doneAt: 0.62,
      logs: isCustom
        ? ["▸ web.search('동창회 dress code')", "▸ 4 sources fetched", "▸ tier=tier2_live", "▸ weather.api → 8.5°C, precip 5%"]
        : ["▸ rag.search('business_meeting')", "▸ tier=tier1, score=0.91", "▸ weather.api → 8.5°C, precip 5%", "▸ thermal_band=cold"],
    },
    {
      id: "rec", agent: "RECOMMEND", label: "17개 체크 항목 평가",
      startAt: 0.62, doneAt: 0.88,
      logs: [
        "▸ group A (dresscode) → 3/5 pass",
        "▸ group B (consistency) → 2/3 pass",
        "▸ group C (color) → 2/3 pass",
        "▸ group D (environment) → 1/2 pass",
        "▸ overall = 69 (no cap)",
      ],
    },
    {
      id: "narrator", agent: "NARRATOR", label: "결과 · 개선 제안 생성",
      startAt: 0.88, doneAt: 1.0,
      logs: [
        "▸ map failed → suggestion (3 created)",
        "▸ sg_1 ΔE+10  sg_2 ΔE+5  sg_3 ΔE+5",
        "▸ rendering ko-KR summary…",
        "▸ done",
      ],
    },
  ];
}

const isMock = import.meta.env.VITE_API_ADAPTER === "mock";

export default function AnalyzingPage() {
  const state = useSessionState();
  const { reset } = useSession();
  const navigate = useNavigate();

  const isCustom = state.status === "loading" ? state.isCustomEvent : false;
  const expectedMs = isMock ? 2400 : isCustom ? 13000 : 8000;
  const overtimeMs = isMock ? 4000 : isCustom ? 18000 : 10000;
  const stages = buildStages(isCustom);

  const [elapsed, setElapsed] = useState(0);
  const [tick, setTick] = useState(0);
  const [overtime, setOvertime] = useState(false);

  useEffect(() => {
    if (state.status === "idle") navigate("/", { replace: true });
  }, [state.status, navigate]);
  useEffect(() => {
    if (state.status === "success") navigate("/result", { replace: true });
  }, [state.status, navigate]);

  useEffect(() => {
    if (state.status !== "loading") return;
    const id = setInterval(() => setElapsed((e) => e + 100), 100);
    return () => clearInterval(id);
  }, [state.status]);
  useEffect(() => {
    if (state.status !== "loading") return;
    const id = setInterval(() => setTick((t) => t + 1), 280);
    return () => clearInterval(id);
  }, [state.status]);
  useEffect(() => {
    if (elapsed >= overtimeMs) setOvertime(true);
  }, [elapsed, overtimeMs]);

  const progress = Math.min(elapsed / expectedMs, 0.99);
  const elapsedSec = (elapsed / 1000).toFixed(1);
  const overallPct = Math.round(progress * 100);

  if (state.status === "error") {
    const msg = state.errorCode ? (ERROR_MESSAGES[state.errorCode] ?? state.error.message) : state.error.message;
    return (
      <div className="min-h-screen bg-canvas">
        <TopNav step="analyzing" />
        <div className="max-w-md mx-auto px-4 py-20" role="alert">
          <div className="bg-panel border border-accent-red/30 rounded-2xl p-7 space-y-4 animate-fade-in-up">
            <Pill tone="red">FAULT · agent_failed</Pill>
            <p className="text-base font-semibold text-ink">분석 실패</p>
            <p className="text-sm text-mute leading-relaxed font-mono">{msg}</p>
            <button
              onClick={reset}
              className="w-full py-2.5 rounded-md bg-accent-blue text-canvas text-xs font-mono uppercase tracking-[0.1em] font-semibold hover:opacity-90 transition-opacity"
            >
              retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  // build cumulative log
  const visibleLogs: { stage: string; line: string }[] = [];
  stages.forEach((st) => {
    if (progress >= st.startAt) {
      const stageProgress = Math.min(1, (progress - st.startAt) / (st.doneAt - st.startAt));
      const linesShown = Math.ceil(stageProgress * st.logs.length);
      st.logs.slice(0, linesShown).forEach((line) => visibleLogs.push({ stage: st.agent, line }));
    }
  });

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav step="analyzing" />
      <main className="max-w-3xl mx-auto px-4 py-8">

        {/* Header */}
        <div className="mb-6 animate-fade-in">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-blue animate-blink" />
            <span className="font-mono text-[10px] text-accent-blue tracking-[0.18em] uppercase">running pipeline</span>
            <div className="flex-1" />
            <span className="font-mono text-[10px] text-stone">elapsed {elapsedSec}s · {overallPct}%</span>
          </div>
          <h1 className="text-2xl font-semibold text-ink tracking-tight">분석 실행 중</h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[1fr_1.2fr] gap-3">

          {/* Stages */}
          <div className="bg-panel border border-hairline2 rounded-xl p-4 space-y-3.5">
            <div className="flex items-center gap-2 pb-2 border-b border-hairline">
              <span className="font-mono text-[9px] text-stone tracking-[0.12em]">01</span>
              <span className="text-[11px] text-body uppercase tracking-[0.18em] font-semibold">stages</span>
            </div>
            {stages.map((st, i) => {
              const sp = Math.max(0, Math.min(1, (progress - st.startAt) / (st.doneAt - st.startAt)));
              const done = progress >= st.doneAt;
              const active = progress >= st.startAt && !done;
              return (
                <div key={st.id} className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-stone w-4">{String(i + 1).padStart(2, "0")}</span>
                    <span className={`text-[12px] ${done ? "text-stone line-through decoration-stone/40" : active ? "text-ink" : "text-stone/60"}`}>
                      {st.label}
                    </span>
                    <div className="flex-1" />
                    <span className={`font-mono text-[9px] ${done ? "text-accent-green" : active ? "text-accent-blue" : "text-stone"}`}>
                      {done ? "DONE" : active ? "RUN" : "WAIT"}
                    </span>
                  </div>
                  <div className="ml-6 h-[3px] rounded-full bg-canvas overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${done ? "bg-accent-green" : "bg-accent-blue"}`}
                      style={{ width: `${sp * 100}%`, boxShadow: active ? "0 0 8px #57c1ff" : "none" }}
                    />
                  </div>
                  <div className="ml-6 flex items-center gap-2">
                    <Pill tone={done ? "green" : active ? "blue" : "mute"} className="!text-[8px]">{st.agent}</Pill>
                    <span className="font-mono text-[9px] text-stone">
                      {Math.round(sp * 100)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Log stream */}
          <div className="bg-canvas border border-hairline2 rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-2 border-b border-hairline bg-panel">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-stone/40" />
                <span className="w-2 h-2 rounded-full bg-stone/40" />
                <span className="w-2 h-2 rounded-full bg-stone/40" />
              </div>
              <span className="font-mono text-[10px] text-stone ml-1">stream.log</span>
              <div className="flex-1" />
              <span className="font-mono text-[9px] text-stone">{visibleLogs.length} lines</span>
            </div>
            <div className="p-3 font-mono text-[10.5px] leading-[1.65] h-[280px] overflow-y-auto" aria-live="polite">
              {visibleLogs.map((l, i) => (
                <div key={i} className="flex gap-2 animate-fade-in">
                  <span className="text-stone/60 w-12 flex-shrink-0">[{l.stage.padEnd(8)}]</span>
                  <span className="text-body">{l.line}</span>
                </div>
              ))}
              <div className="flex gap-2 mt-0.5">
                <span className="text-stone/60 w-12">[…]</span>
                <span className="text-accent-blue">{tick % 4 === 0 ? "▏" : tick % 4 === 1 ? "▎" : tick % 4 === 2 ? "▍" : "▎"}</span>
              </div>
            </div>
          </div>
        </div>

        {overtime && (
          <div className="mt-3 flex items-center gap-2 text-[11px] text-accent-yellow bg-accent-yellow-soft border border-accent-yellow/25 rounded-md px-3 py-2 animate-fade-in font-mono" role="status">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-yellow animate-blink" />
            예상보다 오래 걸리고 있어요 — 잠시만 기다려 주세요
          </div>
        )}
      </main>
    </div>
  );
}
