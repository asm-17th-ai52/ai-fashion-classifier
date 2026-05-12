import { useEffect } from "react";
import { FormProvider, useForm, useFormContext } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { UploadFormSchema } from "@/api/schemas";
import type { UploadFormValues } from "@/api/schemas";
import { STANDARD_EVENT_LABELS } from "@/api/schemas";
import { useSession } from "@/hooks/useSession";
import { useSessionState } from "@/store/sessionContext";
import ImageDropzone from "@/components/ImageDropzone";
import EventForm from "@/components/EventForm";
import TopNav from "@/components/TopNav";
import SectionHead from "@/components/SectionHead";
import Pill from "@/components/Pill";

function ContextPreview() {
  const { watch } = useFormContext<UploadFormValues>();
  const eventType = watch("event_type");
  const datetime = watch("event_datetime");
  const cityCode = watch("city_code");
  const isIndoor = watch("is_indoor");
  const liveResearch = watch("allow_live_research");
  const isCustom = watch("event_type_is_custom");
  const image = watch("image");

  const eventLabel = !eventType
    ? "—"
    : isCustom
    ? eventType
    : STANDARD_EVENT_LABELS[eventType as keyof typeof STANDARD_EVENT_LABELS] ?? eventType;

  const tier = !eventType ? "—" : isCustom && liveResearch ? "tier2_live" : "tier1_rag";
  const dt = datetime ? new Date(datetime) : null;
  const month = dt ? dt.getMonth() + 1 : null;
  const thermalGuess =
    month == null ? "—" : month <= 2 || month === 12 ? "cold" : month <= 4 || month >= 11 ? "cool" : month <= 9 ? "warm" : "mild";

  const rows: [string, string, "blue" | "mute" | "yellow"][] = [
    ["EVENT", eventLabel, eventType ? "blue" : "mute"],
    ["TIER", tier, eventType ? (tier === "tier2_live" ? "yellow" : "blue") : "mute"],
    ["CITY", cityCode || "—", cityCode ? "blue" : "mute"],
    ["WHEN", dt ? `${dt.getMonth() + 1}/${dt.getDate()} ${String(dt.getHours()).padStart(2, "0")}:${String(dt.getMinutes()).padStart(2, "0")}` : "—", dt ? "blue" : "mute"],
    ["INDOOR", isIndoor ? "yes" : "no", "mute"],
    ["THERMAL", thermalGuess, dt ? "blue" : "mute"],
    ["IMAGE", image ? `${(image.size / 1024).toFixed(0)}KB` : "—", image ? "blue" : "mute"],
  ];

  return (
    <div className="bg-panel border border-hairline2 rounded-xl p-4 sticky top-16">
      <SectionHead idx="03" label="derived context" />
      <div className="space-y-1.5 font-mono">
        {rows.map(([k, v, tone]) => (
          <div key={k} className="flex items-center justify-between text-[10.5px]">
            <span className="text-stone tracking-[0.06em]">{k}</span>
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
  const navigate = useNavigate();

  useEffect(() => {
    if (state.status === "success") navigate("/result");
  }, [state.status, navigate]);

  const methods = useForm<UploadFormValues>({
    resolver: zodResolver(UploadFormSchema),
    defaultValues: {
      event_type_is_custom: false,
      is_indoor: false,
      allow_live_research: true,
    },
  });
  const { handleSubmit, formState: { isValid } } = methods;

  return (
    <div className="min-h-screen bg-canvas">
      <TopNav step="upload" />

      <main className="max-w-5xl mx-auto px-4 py-8">

        {/* Hero */}
        <div className="mb-7 animate-fade-in">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-blink" />
            <span className="font-mono text-[10px] text-accent-green tracking-[0.18em] uppercase">17 checks · live</span>
          </div>
          <h1 className="text-[2rem] font-semibold text-ink tracking-tight leading-[1.15]">
            지금 착장, 지금 상황에 맞나요?
          </h1>
          <p className="text-sm text-mute mt-2 font-mono">
            ▸ 사진 + 일정 → AI가 17개 항목으로 적합도 분석
          </p>
        </div>

        <FormProvider {...methods}>
          <form onSubmit={handleSubmit(submit)} noValidate>
            <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr_0.9fr] gap-3 animate-fade-in-up">

              {/* Image */}
              <div className="bg-panel border border-hairline2 rounded-xl p-4">
                <SectionHead idx="01" label="outfit image" />
                <ImageDropzone />
              </div>

              {/* Event form */}
              <div className="bg-panel border border-hairline2 rounded-xl p-4">
                <SectionHead idx="02" label="event metadata" />
                <EventForm />
              </div>

              {/* Context preview */}
              <ContextPreview />
            </div>

            <div className="mt-3 animate-fade-in-up delay-100">
              <button
                type="submit"
                disabled={!isValid}
                className={`w-full py-3.5 rounded-xl text-[12px] font-mono uppercase tracking-[0.18em] font-semibold transition-all duration-200 focus:outline-none ${
                  isValid
                    ? "bg-accent-blue text-canvas shadow-glow-cta hover:shadow-[0_0_36px_rgba(87,193,255,0.45)] hover:-translate-y-px active:scale-[0.99]"
                    : "bg-panelHi text-stone cursor-not-allowed border border-hairline2"
                }`}
              >
                {isValid ? "▸ run analysis pipeline" : "fill all fields to continue"}
              </button>
            </div>
          </form>
        </FormProvider>
      </main>
    </div>
  );
}
