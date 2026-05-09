interface SectionHeadProps {
  idx: string;
  label: string;
  action?: React.ReactNode;
}

export default function SectionHead({ idx, label, action }: SectionHeadProps) {
  return (
    <div className="flex items-center gap-2.5 pb-2.5 mb-3.5 border-b border-hairline">
      <span className="font-mono text-[10px] text-stone tracking-[0.12em]">{idx}</span>
      <span className="text-[11px] text-body uppercase tracking-[0.18em] font-semibold">{label}</span>
      <div className="flex-1 h-px bg-hairline" />
      {action}
    </div>
  );
}
