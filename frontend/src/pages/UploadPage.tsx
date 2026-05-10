import { useEffect } from "react";
import { FormProvider, useForm, useFormContext } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { UploadFormSchema, STANDARD_EVENT_LABELS } from "@/api/schemas";
import type { UploadFormValues } from "@/api/schemas";
import { useSession } from "@/hooks/useSession";
import { useSessionState } from "@/store/sessionContext";
import ImageDropzone from "@/components/ImageDropzone";
import EventForm from "@/components/EventForm";
import TopNav from "@/components/TopNav";
import SectionHead from "@/components/SectionHead";
import Pill from "@/components/Pill";

/* Derived context preview — reads form values and infers pipeline metadata */
function ContextPreview() {
  const { watch } = useFormContext<UploadFormValues>();
  const eventType    = watch("event_type");
  const liveResearch = watch("allow_live_research");
  const isCustom     = watch("event_type_is_custom");

  const eventLabel = !eventType
    ? "—"
    : isCustom
    ? eventType
    : (STANDARD_EVENT_LABELS[eventType as keyof typeof STANDARD_EVENT_LABELS] ?? eventType);

  const tier = !eventType ? "—" : (isCustom && liveResearch) ? "tier2_live" : "tier1_rag";

  const rows: [string, string, "blue" | "mute" | "yellow" | "green"][] = [
    ["dress_code.tier", tier,               tier !== "—" ? "green" : "mute"],
    ["event_type",      eventLabel,         eventType ? "blue" : "mute"],
  ];

  return (
    <div className="bg-panel border border-hairline rounded-xl p-5">
      <SectionHead idx="03" label="DERIVED CONTEXT" />
      <div className="font-mono text-[11px] space-y-2">
        {rows.map(([k, v, tone]) => (
          <div key={k} className="flex items-center justify-between">
            <span className="text-stone">{k}</span>
            <Pill tone={tone}>{v}</Pill>
          </div>
        ))}
      </div>
      <div className="mt-4 pt-3 border-t border-hairline">
        <div className="font-mono text-[9px] text-stone uppercase tracking-[0.12em] mb-1.5">pipeline</div>
        <div className="font-mono text-[10px] text-mute leading-relaxed">
          ▸ vision (~2s)<br />
          ▸ context ({tier === "tier2_live" ? "+5s live" : "rag"})<br />
          ▸ recommend (~2s)<br />
          ▸ narrator (~1s)
        </div>
      </div>
    </div>
  );
}

export default function UploadPage() {
  const state = useSessionState();
  const { submit } = useSession();
  const navigate   = useNavigate();

  useEffect(() => {
    if (state.status === "success") navigate("/result");
  }, [state.status, navigate]);

  const methods = useForm<UploadFormValues>({
    resolver: zodResolver(UploadFormSchema),
    mode: "onChange",
    defaultValues: { event_type_is_custom: false, allow_live_research: true },
  });
  const { handleSubmit, watch, formState: { isValid } } = methods;
  const hasImage = !!watch("image");

  return (
    <div className="min-h-screen bg-canvas text-body font-sans">
      <TopNav step="upload" />

      {/* ── Hero strip ─────────────────────────────────────────── */}
      <div
        className="px-8 py-8 border-b border-hairline"
        style={{
          background:
            "radial-gradient(ellipse 60% 80% at 20% 0%, rgba(95,184,255,0.06) 0%, transparent 70%)",
        }}
      >
        <div className="flex items-end gap-6 max-w-5xl mx-auto">
          <div className="flex-1">
            <div className="flex gap-2 mb-3">
              <Pill tone="blue">● new session</Pill>
              <Pill>17 binary checks</Pill>
            </div>
            <h1
              className="text-[2.4rem] font-semibold text-ink leading-[1.1] tracking-tight m-0"
            >
              지금 착장,<br />
              <span className="text-mute">지금 상황에</span> 맞나요?
            </h1>
          </div>
          <div className="w-72 pb-1">
            <p className="text-xs text-mute leading-relaxed m-0">
              Vision · Context · Recommendation 세 단계 에이전트가<br />
              17개 결정적 체크로 적합도를 산출합니다.
            </p>
            <div className="flex gap-2 mt-3">
              <Pill>vision</Pill>
              <Pill>context</Pill>
              <Pill>rec</Pill>
            </div>
          </div>
        </div>
      </div>

      {/* ── Main form ──────────────────────────────────────────── */}
      <FormProvider {...methods}>
        <form onSubmit={handleSubmit(submit)} noValidate>
          <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-5 p-8 max-w-5xl mx-auto animate-fade-in">

            {/* Left: image */}
            <div className="bg-panel border border-hairline rounded-xl p-5">
              <SectionHead idx="01" label="OUTFIT IMAGE" />
              <ImageDropzone />
            </div>

            {/* Right: form + derived + CTA stacked */}
            <div className="flex flex-col gap-4">
              <div className="bg-panel border border-hairline rounded-xl p-5">
                <SectionHead idx="02" label="EVENT CONTEXT" />
                <EventForm />
              </div>

              <ContextPreview />

              <button
                type="submit"
                disabled={!isValid}
                className={`w-full py-3.5 rounded-xl text-sm font-semibold tracking-wide transition-all duration-200 focus:outline-none flex items-center justify-between px-5 ${
                  isValid
                    ? "bg-accent-blue text-[#001520] shadow-glow-cta hover:shadow-[0_0_36px_rgba(95,184,255,0.5)] hover:-translate-y-px active:scale-[0.99]"
                    : "bg-panelHi text-stone cursor-not-allowed border border-hairline2"
                }`}
              >
                <span>{isValid ? "RUN ANALYSIS" : !hasImage ? "이미지를 업로드해 주세요" : "일정 정보를 입력해 주세요"}</span>
                {isValid && (
                  <span className="font-mono text-[11px] opacity-70">↵ ENTER</span>
                )}
              </button>
            </div>
          </div>
        </form>
      </FormProvider>
    </div>
  );
}
