type Tone = "mute" | "blue" | "green" | "red" | "yellow";

const TONE: Record<Tone, string> = {
  mute:   "bg-panelHi text-body border-hairline2",
  blue:   "bg-accent-blue-soft text-accent-blue border-accent-blue/25",
  green:  "bg-accent-green-soft text-accent-green border-accent-green/25",
  red:    "bg-accent-red-soft text-accent-red border-accent-red/25",
  yellow: "bg-accent-yellow-soft text-accent-yellow border-accent-yellow/25",
};

interface PillProps {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}

export default function Pill({ children, tone = "mute", className = "" }: PillProps) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded-md text-[10.5px] font-mono uppercase tracking-[0.04em] border ${TONE[tone]} ${className}`}>
      {children}
    </span>
  );
}
