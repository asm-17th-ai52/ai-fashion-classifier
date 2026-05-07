import Pill from "./Pill";

interface ScoreGaugeProps {
  score: number;
  capApplied: "blocker_cap_50" | null;
  simulatedScore?: number | null;
}

function scoreTone(s: number) {
  if (s < 30) return { stroke: "#ff6161", text: "text-score-low",  label: "낮음",     pillTone: "red" as const };
  if (s < 60) return { stroke: "#ffc533", text: "text-score-mid",  label: "주의",     pillTone: "yellow" as const };
  if (s < 80) return { stroke: "#57c1ff", text: "text-score-good", label: "적합",     pillTone: "blue" as const };
  return        { stroke: "#59d499", text: "text-score-high", label: "매우 적합", pillTone: "green" as const };
}

export default function ScoreGauge({ score, capApplied, simulatedScore }: ScoreGaugeProps) {
  const display = simulatedScore ?? score;
  const tone = scoreTone(display);
  const isSim = simulatedScore != null;
  const delta = isSim ? display - score : 0;
  const circ = 2 * Math.PI * 70;
  const dash = (display / 100) * circ;

  return (
    <div className="relative">
      <div
        className="absolute inset-0 pointer-events-none rounded-2xl"
        style={{ background: `radial-gradient(ellipse 80% 60% at 50% 100%, ${tone.stroke}1f 0%, transparent 70%)` }}
      />

      <div className="relative">
        <div className="relative w-[200px] h-[200px] mx-auto my-2">
          <svg width="200" height="200" viewBox="0 0 200 200" aria-label={`종합 점수 ${display}점`}>
            {/* 60 ticks */}
            {Array.from({ length: 60 }).map((_, i) => {
              const angle = -90 + (i / 60) * 360;
              const rad = (angle * Math.PI) / 180;
              const r1 = 88, r2 = i % 5 === 0 ? 78 : 82;
              return (
                <line
                  key={i}
                  x1={100 + Math.cos(rad) * r1}
                  y1={100 + Math.sin(rad) * r1}
                  x2={100 + Math.cos(rad) * r2}
                  y2={100 + Math.sin(rad) * r2}
                  stroke="#2a2f3e"
                  strokeWidth="0.6"
                />
              );
            })}
            <circle cx="100" cy="100" r="70" fill="none" stroke="#1f2330" strokeWidth="6" />
            <circle
              cx="100" cy="100" r="70" fill="none"
              stroke={tone.stroke} strokeWidth="6"
              strokeDasharray={`${dash} ${circ}`}
              strokeLinecap="round"
              transform="rotate(-90 100 100)"
              style={{ transition: "stroke-dasharray 0.6s ease", filter: `drop-shadow(0 0 8px ${tone.stroke})` }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-[12px] text-stone font-mono tracking-[0.1em]">overall</div>
            <div className="text-[56px] font-bold text-ink leading-none tabular-nums tracking-tight">{display}</div>
            <div className="text-[11px] text-mute mt-0.5 font-mono">/100</div>
            {isSim && (
              <div className={`absolute bottom-2.5 text-[10px] font-mono ${delta > 0 ? "text-accent-green" : "text-accent-red"}`}>
                {delta > 0 ? "+" : ""}{delta} sim
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-between items-center mt-1">
          <div className="flex gap-1.5">
            <Pill tone={tone.pillTone}>{tone.label}</Pill>
            {capApplied === "blocker_cap_50" && !isSim && (
              <Pill tone="red">핵심 미스 캡</Pill>
            )}
          </div>
          <span className="font-mono text-[10px] text-stone">group_weighted_v1</span>
        </div>
      </div>
    </div>
  );
}
