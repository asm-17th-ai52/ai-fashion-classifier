import { useState, useEffect, useRef } from "react";

const WEEK = ["일", "월", "화", "수", "목", "금", "토"];

function calendarGrid(year: number, month: number) {
  const firstDow = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrev = new Date(year, month, 0).getDate();
  const cells: { day: number; cur: boolean }[] = [];
  for (let i = firstDow - 1; i >= 0; i--) cells.push({ day: daysInPrev - i, cur: false });
  for (let d = 1; d <= daysInMonth; d++) cells.push({ day: d, cur: true });
  while (cells.length < 42) cells.push({ day: cells.length - firstDow - daysInMonth + 1, cur: false });
  return cells;
}

function toIso(year: number, month: number, day: number) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function formatDisplay(iso: string) {
  const d = new Date(iso + "T12:00");
  return d.toLocaleDateString("ko-KR", {
    year: "numeric", month: "long", day: "numeric", weekday: "short",
  });
}

interface DatePickerProps {
  value: string; // "YYYY-MM-DD" or ""
  onChange: (v: string) => void;
}

export default function DatePicker({ value, onChange }: DatePickerProps) {
  const today = new Date();
  const todayIso = toIso(today.getFullYear(), today.getMonth(), today.getDate());

  const initFrom = value || todayIso;
  const [viewYear, setViewYear] = useState(() => parseInt(initFrom.slice(0, 4)));
  const [viewMonth, setViewMonth] = useState(() => parseInt(initFrom.slice(5, 7)) - 1);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function down(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", down);
    return () => document.removeEventListener("mousedown", down);
  }, [open]);

  function prev() {
    if (viewMonth === 0) { setViewMonth(11); setViewYear((y) => y - 1); }
    else setViewMonth((m) => m - 1);
  }
  function next() {
    if (viewMonth === 11) { setViewMonth(0); setViewYear((y) => y + 1); }
    else setViewMonth((m) => m + 1);
  }
  function pick(day: number) {
    onChange(toIso(viewYear, viewMonth, day));
    setOpen(false);
  }

  const cells = calendarGrid(viewYear, viewMonth);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`w-full rounded-lg px-3 py-2 text-left font-mono text-[12px] border transition-all flex items-center justify-between gap-2 ${
          open
            ? "bg-canvas border-accent-blue/50 text-body"
            : value
            ? "bg-canvas border-hairline text-body hover:border-hairline2"
            : "bg-canvas border-hairline text-stone/50 hover:border-hairline2 hover:text-stone"
        }`}
      >
        <span>{value ? formatDisplay(value) : "날짜 선택…"}</span>
        <svg
          className={`w-3 h-3 flex-shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 12 12" fill="none"
        >
          <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {open && (
        <div
          className="absolute z-20 top-[calc(100%+4px)] left-0 right-0 rounded-xl border border-hairline overflow-hidden animate-fade-in"
          style={{ background: "#06070a" }}
        >
          {/* Month nav */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-hairline">
            <button
              type="button"
              onClick={prev}
              className="w-6 h-6 flex items-center justify-center rounded text-stone hover:text-ink hover:bg-hairline transition-all font-mono text-sm"
            >
              ‹
            </button>
            <span className="font-mono text-[11px] text-body tracking-wider">
              {viewYear}년 {viewMonth + 1}월
            </span>
            <button
              type="button"
              onClick={next}
              className="w-6 h-6 flex items-center justify-center rounded text-stone hover:text-ink hover:bg-hairline transition-all font-mono text-sm"
            >
              ›
            </button>
          </div>

          <div className="p-2.5">
            {/* Weekday row */}
            <div className="grid grid-cols-7 mb-1">
              {WEEK.map((d, i) => (
                <div
                  key={d}
                  className={`text-center font-mono text-[9px] py-1 ${
                    i === 0 ? "text-accent-red/50" : i === 6 ? "text-accent-blue/50" : "text-stone"
                  }`}
                >
                  {d}
                </div>
              ))}
            </div>

            {/* Day cells */}
            <div className="grid grid-cols-7 gap-y-0.5">
              {cells.map((cell, i) => {
                if (!cell.cur) {
                  return (
                    <div key={i} className="h-7 flex items-center justify-center font-mono text-[10px] text-stone/20">
                      {cell.day}
                    </div>
                  );
                }
                const iso = toIso(viewYear, viewMonth, cell.day);
                const isSelected = iso === value;
                const isToday = iso === todayIso;
                const dow = new Date(iso + "T12:00").getDay();
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => pick(cell.day)}
                    className={`h-7 rounded-md font-mono text-[11px] transition-all ${
                      isSelected
                        ? "bg-accent-blue text-[#001520] font-semibold"
                        : isToday
                        ? "border border-accent-blue/40 text-accent-blue hover:bg-accent-blue-soft"
                        : dow === 0
                        ? "text-accent-red/60 hover:bg-hairline"
                        : dow === 6
                        ? "text-accent-blue/60 hover:bg-hairline"
                        : "text-body hover:bg-hairline"
                    }`}
                  >
                    {cell.day}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
