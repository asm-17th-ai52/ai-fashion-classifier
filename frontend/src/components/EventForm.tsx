import { useFormContext } from "react-hook-form";
import type { UploadFormValues, StandardEventType } from "@/api/schemas";
import { STANDARD_EVENT_LABELS } from "@/api/schemas";

const STANDARD_KEYS = Object.keys(STANDARD_EVENT_LABELS) as StandardEventType[];
const CUSTOM_SENTINEL = "__custom__";

const labelCls =
  "block text-[10px] font-semibold text-stone uppercase tracking-[0.14em] mb-2";

const inputCls =
  "w-full rounded-lg bg-canvas border border-hairline text-body text-[12px] px-3 py-2 font-mono focus:outline-none focus:border-accent-blue/50 focus:ring-1 focus:ring-accent-blue/20 transition-all placeholder-stone/50";

export default function EventForm() {
  const { register, setValue, watch, formState: { errors } } = useFormContext<UploadFormValues>();

  const eventType = watch("event_type");
  const isCustom  = watch("event_type_is_custom");
  const allowLive = watch("allow_live_research");

  const sv: typeof setValue = (name, value) =>
    setValue(name, value as never, { shouldValidate: true, shouldDirty: true });

  const selectedKey = isCustom ? CUSTOM_SENTINEL : eventType;

  function selectEventType(val: string) {
    if (val === CUSTOM_SENTINEL) {
      sv("event_type_is_custom", true);
      sv("event_type", "");
    } else {
      sv("event_type_is_custom", false);
      sv("event_type", val);
    }
  }

  const pillBase = "rounded-lg px-2 py-2 text-[11px] font-mono text-center transition-all leading-snug border";
  const pillActive = "bg-accent-blue-soft border-accent-blue text-accent-blue";
  const pillIdle = "bg-canvas border-hairline text-stone hover:border-hairline2 hover:text-body";

  return (
    <div className="space-y-5">

      {/* ── 일정 유형 ── */}
      <div>
        <div className={labelCls}>
          일정 유형 <span className="text-accent-red normal-case tracking-normal">*</span>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {STANDARD_KEYS.map((k) => (
            <button key={k} type="button" onClick={() => selectEventType(k)}
              className={`${pillBase} ${selectedKey === k ? pillActive : pillIdle}`}
            >
              {STANDARD_EVENT_LABELS[k]}
            </button>
          ))}
          <button type="button" onClick={() => selectEventType(CUSTOM_SENTINEL)}
            className={`${pillBase} col-span-3 ${
              selectedKey === CUSTOM_SENTINEL
                ? "bg-accent-yellow-soft border-accent-yellow/50 text-accent-yellow"
                : pillIdle
            }`}
          >
            직접 입력 ▸
          </button>
        </div>

        {isCustom && (
          <div className="mt-2 space-y-1.5 animate-fade-in">
            <input
              {...register("event_type")}
              placeholder="예: 동창회, 졸업 파티, 팀 회식…"
              className={inputCls}
              aria-label="직접 입력: 일정 유형"
            />
            <p className="text-[10px] text-accent-yellow bg-accent-yellow-soft border border-accent-yellow/20 rounded-lg px-2.5 py-1.5 font-mono">
              외부 자료를 실시간 검색해 분석합니다 (+5초)
            </p>
          </div>
        )}
        {errors.event_type && (
          <p role="alert" className="text-[11px] text-accent-red mt-1.5">{errors.event_type.message}</p>
        )}
      </div>

      {/* ── 실시간 외부 검색 ── */}
      <div className="flex items-center justify-between pt-0.5">
        <div>
          <div className="text-[11px] text-body font-mono">실시간 외부 검색</div>
          {!allowLive && (
            <div className="text-[10px] text-stone mt-0.5 animate-fade-in">일반 가이드로 분석됩니다</div>
          )}
        </div>
        <button
          type="button" role="switch" aria-checked={allowLive}
          onClick={() => sv("allow_live_research", !allowLive)}
          aria-label="실시간 외부 자료 검색 토글"
          className={`relative inline-flex h-5 w-9 items-center rounded-full transition-all duration-200 focus:outline-none focus:ring-1 focus:ring-accent-blue/40 ${
            allowLive ? "bg-accent-blue" : "bg-hairline2"
          }`}
        >
          <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform duration-200 ${
            allowLive ? "translate-x-5" : "translate-x-0.5"
          }`} />
        </button>
      </div>

    </div>
  );
}
