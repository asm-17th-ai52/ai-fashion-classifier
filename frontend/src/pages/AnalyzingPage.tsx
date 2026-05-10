import { useEffect } from "react";
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

// pct 구간 → 에이전트 단계 매핑 (시각 전용, SSE message가 진짜 내용)
const STAGES = [
  { id: "vision",    label: "garment detection", start: 0,  end: 35  },
  { id: "context",   label: "dress code retrieval",    start: 35, end: 65  },
  { id: "rec",       label: "17 binary checks",  start: 65, end: 88  },
  { id: "narrator",  label: "fix mapping",        start: 88, end: 100 },
];

const AGENT_COLORS: Record<string, string> = {
  vision:   "#5fb8ff",
  context:  "#fbbf57",
  rec:      "#6ee7a7",
  narrator: "#c084fc",
};

const AGENT_LABELS: Record<string, string> = {
  vision:   "VISION",
  context:  "CONTEXT",
  rec:      "RECOMMEND",
  narrator: "NARRATOR",
};

export default function AnalyzingPage() {
  const state = useSessionState();
  const { reset } = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (state.status === "idle") navigate("/", { replace: true });
  }, [state.status, navigate]);

  useEffect(() => {
    if (state.status === "success") navigate("/result", { replace: true });
  }, [state.status, navigate]);

  const progress = state.status === "loading" ? state.progress : 0;
  const logs     = state.status === "loading" ? state.logs : [];
  const overtime = progress > 0 && progress < 100 && logs.length > 12;

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
            <Pill tone="blue">{progress}%</Pill>
          </div>

          {/* 4-agent card grid */}
          <div className="bg-panel border border-hairline rounded-xl p-4 mb-4 animate-fade-in">
            <div className="grid grid-cols-4 gap-3">
              {STAGES.map((st) => {
                const sp     = Math.max(0, Math.min(1, (progress - st.start) / (st.end - st.start)));
                const pct    = Math.round(sp * 100);
                const done   = progress >= st.end;
                const active = progress >= st.start && !done;
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
                        {AGENT_LABELS[st.id]}
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

            {/* Overall progress bar */}
            <div className="mt-4 h-[3px] rounded-full bg-canvas overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${progress}%`,
                  background: "linear-gradient(to right, #5fb8ff, #6ee7a7)",
                  boxShadow: "0 0 8px rgba(95,184,255,0.4)",
                }}
              />
            </div>
          </div>

          {/* Terminal log — SSE messages */}
          <div className="rounded-xl overflow-hidden border border-hairline animate-fade-in" style={{ background: "#06070a" }}>
            <div className="flex items-center gap-2 px-4 py-2 border-b border-hairline bg-panel">
              <span className="w-2 h-2 rounded-full" style={{ background: "#ff5f57" }} />
              <span className="w-2 h-2 rounded-full" style={{ background: "#febc2e" }} />
              <span className="w-2 h-2 rounded-full" style={{ background: "#28c840" }} />
              <span className="font-mono text-[10px] text-stone ml-2">agent.log</span>
              <div className="flex-1" />
              <span className="font-mono text-[10px] text-stone">
                live · {logs.length} lines
              </span>
            </div>
            <div
              className="p-4 font-mono text-[10.5px] leading-[1.65] overflow-y-auto relative"
              style={{ height: 260 }}
              aria-live="polite"
            >
              <div
                className="absolute top-0 left-0 right-0 h-8 pointer-events-none z-10"
                style={{ background: "linear-gradient(to bottom, #06070a, transparent)" }}
              />
              {logs.slice(-14).map((msg, i) => {
                // 어느 에이전트 구간인지 추론 (시각 전용)
                const logPct = progress;
                const stage = STAGES.find(
                  (s) => logPct >= s.start && logPct < s.end
                ) ?? STAGES[STAGES.length - 1];
                const color = AGENT_COLORS[stage.id] ?? "#7c818f";
                const agentLabel = AGENT_LABELS[stage.id] ?? "SYSTEM";
                return (
                  <div key={i} className="flex gap-3">
                    <span
                      className="w-28 flex-shrink-0 text-[9px]"
                      style={{ color }}
                    >
                      [{agentLabel.padEnd(8)}]
                    </span>
                    <span className="text-body">{msg}</span>
                  </div>
                );
              })}
              {/* cursor */}
              <div className="flex gap-3 mt-1">
                <span className="text-stone/60 w-28" />
                <span style={{ color: "#5fb8ff" }}>▏</span>
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
