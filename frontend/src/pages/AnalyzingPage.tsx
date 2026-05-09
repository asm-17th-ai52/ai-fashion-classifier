import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionState } from "@/store/sessionContext";
import { useSession } from "@/hooks/useSession";
import TopNav from "@/components/TopNav";
import Pill from "@/components/Pill";

const ERROR_MESSAGES: Record<string, string> = {
  person_not_detected: "사람이 정면으로 보이는 사진을 사용해 주세요.",
  image_too_large:     "10MB 이하 이미지만 사용 가능합니다.",
  image_invalid:       "이미지를 읽을 수 없습니다. 다른 파일을 시도해 주세요.",
  rate_limited:        "잠시 후 다시 시도해 주세요.",
  agent_failed:        "AI 분석에 실패했어요. 다시 시도해 주세요.",
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
      id: "vision", agent: "VISION", label: "garment detection + attribute extraction",
      startAt: 0, doneAt: 0.3,
      logs: [
        "detecting persons in frame…",
        "ROI: 1 person, frontal=true",
        "garment[top]: dress_shirt · solid",
        "garment[bottom]: chino · solid",
        "garment[shoes]: loafer · solid",
        "formality_label computed",
        "vision.confidence avg=0.87",
      ],
    },
    {
      id: "context", agent: "CONTEXT",
      label: isCustom ? "live web search + dress code" : "weather + dress code retrieval",
      startAt: 0.3, doneAt: 0.62,
      logs: isCustom
        ? ["web.search query built", "4 sources fetched", "tier=tier2_live", "weather.api → ok"]
        : ["rag.search: match=0.91", "weather.fetch: ok", "thermal_band computed", "context assembled"],
    },
    {
      id: "rec", agent: "RECOMMEND", label: "17 binary checks",
      startAt: 0.62, doneAt: 0.88,
      logs: [
        "group A (dresscode) evaluated",
        "group B (consistency) evaluated",
        "group C (color) evaluated",
        "group D (environment) evaluated",
        "group E (confidence) evaluated",
      ],
    },
    {
      id: "narr", agent: "NARRATOR", label: "fix mapping + simulation",
      startAt: 0.88, doneAt: 1.0,
      logs: [
        "map fail → fix actions",
        "simulate Δscores…",
        "rendering ko-KR summary…",
        "done",
      ],
    },
  ];
}

const isMock = import.meta.env.VITE_API_ADAPTER === "mock";

export default function AnalyzingPage() {
  const state = useSessionState();
  const { reset } = useSession();
  const navigate = useNavigate();

  const isCustom  = state.status === "loading" ? state.isCustomEvent : false;
  const expectedMs = isMock ? 2400 : isCustom ? 13000 : 8000;
  const overtimeMs = isMock ? 4000  : isCustom ? 18000 : 10000;
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

  const progress   = Math.min(elapsed / expectedMs, 0.99);
  const overallPct = Math.round(progress * 100);
  const elapsedSec = (elapsed / 1000).toFixed(1);

  /* ── Error ── */
  if (state.status === "error") {
    const msg = state.errorCode
      ? (ERROR_MESSAGES[state.errorCode] ?? state.error.message)
      : state.error.message;
    return (
      <div className="min-h-screen bg-canvas">
        <TopNav step="analyzing" />
        <div className="max-w-md mx-auto px-4 py-20" role="alert">
          <div className="bg-panel border border-accent-red/30 rounded-xl p-7 space-y-4 animate-fade-in">
            <Pill tone="red">FAULT · agent_failed</Pill>
            <p className="text-base font-semibold text-ink">분석 실패</p>
            <p className="text-sm text-mute leading-relaxed font-mono">{msg}</p>
            <button
              onClick={reset}
              className="w-full py-2.5 rounded-lg bg-accent-blue text-[#001520] text-xs font-mono uppercase tracking-[0.1em] font-semibold hover:opacity-90 transition-opacity"
            >
              retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* Build cumulative terminal log */
  const visibleLogs: { agent: string; line: string; ts: string }[] = [];
  stages.forEach((st) => {
    if (progress >= st.startAt) {
      const sp = Math.min(1, (progress - st.startAt) / (st.doneAt - st.startAt));
      const shown = Math.ceil(sp * st.logs.length);
      st.logs.slice(0, shown).forEach((line, i) => {
        const t = (st.startAt * expectedMs / 1000 + i * 0.3);
        visibleLogs.push({ agent: st.agent, line, ts: t.toFixed(1) + "s" });
      });
    }
  });

  const AGENT_COLORS: Record<string, string> = {
    VISION:    "#5fb8ff",
    CONTEXT:   "#fbbf57",
    RECOMMEND: "#6ee7a7",
    NARRATOR:  "#c084fc",
  };

  /* ── Analyzing ── */
  return (
    <div className="min-h-screen bg-canvas text-body font-sans">
      <TopNav step="analyzing" />

      <div
        className="px-8 py-8 min-h-[calc(100vh-48px)]"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(95,184,255,0.04) 0%, transparent 70%)",
        }}
      >
        <div className="max-w-4xl mx-auto">

          {/* Header */}
          <div className="flex items-center gap-3 mb-6 animate-fade-in">
            {/* V1 spinning circle */}
            <div className="relative w-8 h-8 flex-shrink-0">
              <div className="absolute inset-0 rounded-full border-2 border-hairline2" />
              <div
                className="absolute inset-0 rounded-full border-2 animate-spin"
                style={{ borderColor: "transparent", borderTopColor: "#5fb8ff" }}
              />
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-ink">분석 실행 중</div>
              <div className="text-[10px] text-stone font-mono mt-0.5">
                pipeline: vision → context → recommendation → narrator
              </div>
            </div>
            <Pill tone="blue">{overallPct}%</Pill>
            <span className="font-mono text-[10px] text-stone">{elapsedSec}s</span>
          </div>

          {/* 4-agent card grid */}
          <div className="bg-panel border border-hairline rounded-xl p-4 mb-4 animate-fade-in">
            <div className="grid grid-cols-4 gap-3">
              {stages.map((st) => {
                const sp     = Math.max(0, Math.min(1, (progress - st.startAt) / (st.doneAt - st.startAt)));
                const pct    = Math.round(sp * 100);
                const done   = progress >= st.doneAt;
                const active = progress >= st.startAt && !done;
                const color  = done ? "#6ee7a7" : active ? "#5fb8ff" : "#525766";
                return (
                  <div
                    key={st.id}
                    className="rounded-lg p-3 border transition-colors"
                    style={{
                      background: active ? "rgba(95,184,255,0.04)" : "transparent",
                      borderColor: active ? "rgba(95,184,255,0.2)" : "#1f2330",
                    }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-[9px] tracking-[0.1em]" style={{ color }}>
                        {st.agent}
                      </span>
                      <span className="font-mono text-[9px]" style={{ color }}>
                        {done ? "✓" : active ? `${pct}%` : "—"}
                      </span>
                    </div>
                    <div className="h-[2px] rounded-full bg-canvas overflow-hidden mb-2">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${pct}%`,
                          background: color,
                          boxShadow: active ? `0 0 6px ${color}` : "none",
                        }}
                      />
                    </div>
                    <div className="text-[10px] text-stone leading-snug">{st.label}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Terminal log */}
          <div className="rounded-xl overflow-hidden border border-hairline animate-fade-in" style={{ background: "#06070a" }}>
            {/* title bar */}
            <div className="flex items-center gap-2 px-4 py-2 border-b border-hairline bg-panel">
              <span className="w-2 h-2 rounded-full" style={{ background: "#ff5f57" }} />
              <span className="w-2 h-2 rounded-full" style={{ background: "#febc2e" }} />
              <span className="w-2 h-2 rounded-full" style={{ background: "#28c840" }} />
              <span className="font-mono text-[10px] text-stone ml-2">
                ~/sessions/sess_001 · agent.log
              </span>
              <div className="flex-1" />
              <span className="font-mono text-[10px] text-stone">
                live · {visibleLogs.length} lines
              </span>
            </div>
            {/* log lines */}
            <div
              className="p-4 font-mono text-[10.5px] leading-[1.65] overflow-y-auto relative"
              style={{ height: 300 }}
              aria-live="polite"
            >
              {/* top fade */}
              <div
                className="absolute top-0 left-0 right-0 h-8 pointer-events-none z-10"
                style={{ background: "linear-gradient(to bottom, #06070a, transparent)" }}
              />
              {visibleLogs.slice(-14).map((l, i) => (
                <div key={i} className="flex gap-3">
                  <span className="text-stone/60 w-10 flex-shrink-0">{l.ts}</span>
                  <span
                    className="w-28 flex-shrink-0"
                    style={{ color: AGENT_COLORS[l.agent] ?? "#7c818f" }}
                  >
                    [{l.agent.padEnd(8)}]
                  </span>
                  <span className="text-body">{l.line}</span>
                </div>
              ))}
              {/* cursor */}
              <div className="flex gap-3 mt-1">
                <span className="text-stone/60 w-10" />
                <span className="text-stone/60 w-28" />
                <span style={{ color: "#5fb8ff" }}>
                  {["▏", "▎", "▍", "▎"][tick % 4]}
                </span>
              </div>
            </div>
          </div>

          {overtime && (
            <div
              className="mt-3 flex items-center gap-2 text-[11px] text-accent-yellow bg-accent-yellow-soft border border-accent-yellow/25 rounded-lg px-4 py-2.5 font-mono animate-fade-in"
              role="status"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-accent-yellow animate-blink" />
              예상보다 오래 걸리고 있어요 — 잠시만 기다려 주세요
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
