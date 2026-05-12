interface TimePickerProps {
  value: string; // "HH:MM" or ""
  onChange: (v: string) => void;
}

const QUICK = [
  { label: "오전 8시",  h: 8,  m: 0 },
  { label: "낮 12시",   h: 12, m: 0 },
  { label: "오후 3시",  h: 15, m: 0 },
  { label: "저녁 7시",  h: 19, m: 0 },
];

function pad(n: number) { return String(n).padStart(2, "0"); }

export default function TimePicker({ value, onChange }: TimePickerProps) {
  const h = value ? value.slice(0, 2) : "";
  const m = value ? value.slice(3, 5) : "";

  function emitH(raw: string) {
    const n = parseInt(raw);
    if (raw === "") { onChange(m ? `__:${m}` : ""); return; }
    if (isNaN(n) || n < 0 || n > 23) return;
    if (m) onChange(`${pad(n)}:${m}`);
    else onChange(`${pad(n)}:00`);
  }

  function emitM(raw: string) {
    const n = parseInt(raw);
    if (raw === "") { onChange(h ? `${h}:__` : ""); return; }
    if (isNaN(n) || n < 0 || n > 59) return;
    if (h) onChange(`${h}:${pad(n)}`);
    else onChange(`12:${pad(n)}`);
  }

  const numInput =
    "w-14 text-center bg-canvas border border-hairline rounded-lg font-mono text-[20px] font-semibold text-ink py-2 focus:outline-none focus:border-accent-blue/50 focus:ring-1 focus:ring-accent-blue/20 transition-all tabular-nums [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none";

  return (
    <div className="space-y-3">
      {/* Quick presets */}
      <div className="grid grid-cols-4 gap-1.5">
        {QUICK.map((q) => {
          const active = h === pad(q.h) && m === pad(q.m);
          return (
            <button key={q.label} type="button"
              onClick={() => onChange(`${pad(q.h)}:${pad(q.m)}`)}
              className={`rounded-lg py-1.5 text-[11px] font-mono text-center border transition-all ${
                active
                  ? "bg-accent-blue-soft border-accent-blue text-accent-blue"
                  : "bg-canvas border-hairline text-stone hover:border-hairline2 hover:text-body"
              }`}
            >
              {q.label}
            </button>
          );
        })}
      </div>

      {/* HH : MM inputs */}
      <div
        className="flex items-center justify-center gap-2 rounded-xl border border-hairline py-4"
        style={{ background: "#06070a" }}
      >
        <input
          type="number"
          min={0} max={23}
          value={h}
          placeholder="00"
          onChange={(e) => emitH(e.target.value)}
          className={numInput}
          aria-label="시"
        />
        <span className="font-mono text-[24px] text-stone select-none">:</span>
        <input
          type="number"
          min={0} max={59}
          value={m}
          placeholder="00"
          onChange={(e) => emitM(e.target.value)}
          className={numInput}
          aria-label="분"
        />
      </div>

      <div className="flex justify-between font-mono text-[9px] text-stone px-1">
        <span>시 (0–23)</span>
        <span>분 (0–59)</span>
      </div>
    </div>
  );
}
