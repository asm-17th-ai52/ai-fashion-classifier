import type { ApiAdapter } from "../types";
import type { UploadFormValues, SessionResponse, SimulateResponse } from "../schemas";
import { SessionResponseSchema, SimulateResponseSchema } from "../schemas";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function parseResponse<T>(
  res: Response,
  parse: (data: unknown) => T
): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = Object.assign(
      new Error(body?.error?.message ?? res.statusText),
      { status: res.status, body }
    );
    throw err;
  }
  const data = await res.json();
  return parse(data);
}

export class HttpApiAdapter implements ApiAdapter {
  async createSession(form: UploadFormValues): Promise<SessionResponse> {
    const fd = new FormData();
    fd.append("image", form.image);
    fd.append("event_type", form.event_type);
    fd.append("event_type_is_custom", String(form.event_type_is_custom));
    fd.append("event_datetime", form.event_datetime);
    fd.append("city_code", form.city_code);
    fd.append("is_indoor", String(form.is_indoor));
    fd.append("allow_live_research", String(form.allow_live_research));

    const res = await fetch(`${BASE_URL}/v1/sessions`, {
      method: "POST",
      body: fd,
    });
    return parseResponse(res, SessionResponseSchema.parse);
  }

  async simulate(
    sessionId: string,
    appliedSuggestionIds: string[]
  ): Promise<SimulateResponse> {
    const res = await fetch(`${BASE_URL}/v1/sessions/${sessionId}/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ applied_suggestion_ids: appliedSuggestionIds }),
    });
    return parseResponse(res, SimulateResponseSchema.parse);
  }
}
