import type { ApiAdapter } from "../types";
import type { UploadFormValues, CreateSessionResponse, SessionResponse, SimulateResponse } from "../schemas";
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
  // Holds full SessionResponse when backend responds synchronously (no SSE).
  private _syncCache = new Map<string, unknown>();

  async createSession(form: UploadFormValues): Promise<CreateSessionResponse> {
    const fd = new FormData();
    fd.append("image", form.image);
    fd.append("event_type", form.event_type);
    fd.append("event_type_is_custom", String(form.event_type_is_custom));
    fd.append("allow_live_research", String(form.allow_live_research));
    // Backend still requires event_datetime — auto-fill current time.
    fd.append("event_datetime", new Date().toISOString());

    const res = await fetch(`${BASE_URL}/v1/sessions`, {
      method: "POST",
      body: fd,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw Object.assign(
        new Error(body?.error?.message ?? res.statusText),
        { status: res.status, body }
      );
    }

    const data = await res.json() as Record<string, unknown>;

    // Backend may return full SessionResponse synchronously (no SSE endpoint).
    // Cache it so getSession() can return it immediately on EventSource onerror fallback.
    if (data && "recommendation" in data) {
      this._syncCache.set(String(data.session_id), data);
    }

    return { session_id: String(data.session_id) };
  }

  async getSession(sessionId: string): Promise<SessionResponse> {
    // Return synchronously-cached response if available (backend without SSE).
    if (this._syncCache.has(sessionId)) {
      const cached = this._syncCache.get(sessionId);
      this._syncCache.delete(sessionId);
      return SessionResponseSchema.parse(cached);
    }
    const res = await fetch(`${BASE_URL}/v1/sessions/${sessionId}`);
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
