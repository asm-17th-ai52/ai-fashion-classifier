import type { ApiAdapter, StreamCallbacks } from "../types";
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

function extractErrorCode(err: unknown): string | undefined {
  if (err && typeof err === "object" && "body" in err) {
    const body = (err as { body?: { error?: { code?: string } } }).body;
    return body?.error?.code;
  }
  return undefined;
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
    // Cache it so subscribeStream's onerror fallback can return it immediately.
    if (data && "recommendation" in data) {
      this._syncCache.set(String(data.session_id), data);
    }

    return { session_id: String(data.session_id) };
  }

  subscribeStream(sessionId: string, callbacks: StreamCallbacks): () => void {
    const es = new EventSource(`${BASE_URL}/v1/sessions/${sessionId}/stream`);

    es.onmessage = (e) => {
      const ev = JSON.parse(e.data) as {
        type: "progress" | "done" | "error";
        pct: number;
        message: string;
        result?: unknown;
        code?: string;
      };
      if (ev.type === "progress") {
        callbacks.onProgress(ev.pct, ev.message);
      } else if (ev.type === "done") {
        es.close();
        callbacks.onDone(ev.result as SessionResponse);
      } else if (ev.type === "error") {
        es.close();
        callbacks.onError(new Error(ev.message), ev.code);
      }
    };

    es.onerror = () => {
      es.close();
      // 연결 끊김 — GET /v1/sessions/{id} 폴백
      this.getSession(sessionId)
        .then((session) => callbacks.onDone(session))
        .catch((err) => {
          const error = err instanceof Error ? err : new Error(String(err));
          callbacks.onError(error, extractErrorCode(err));
        });
    };

    return () => es.close();
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
