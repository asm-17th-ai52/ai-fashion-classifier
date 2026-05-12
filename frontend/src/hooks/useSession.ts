import { useNavigate } from "react-router-dom";
import { createSession, getSession } from "@/api/client";
import { useSessionDispatch } from "@/store/sessionContext";
import type { UploadFormValues } from "@/api/schemas";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

function extractErrorCode(err: unknown): string | undefined {
  if (err && typeof err === "object" && "body" in err) {
    const body = (err as { body?: { error?: { code?: string } } }).body;
    return body?.error?.code;
  }
  return undefined;
}

let activeEs: EventSource | null = null;

export function useSession() {
  const dispatch = useSessionDispatch();
  const navigate = useNavigate();

  function subscribeToStream(sessionId: string) {
    if (activeEs) {
      activeEs.close();
      activeEs = null;
    }

    const es = new EventSource(`${BASE_URL}/v1/sessions/${sessionId}/stream`);
    activeEs = es;

    es.onmessage = (e) => {
      const ev = JSON.parse(e.data) as {
        type: "progress" | "done" | "error";
        pct: number;
        message: string;
        result?: unknown;
        code?: string;
      };

      if (ev.type === "progress") {
        dispatch({ type: "PROGRESS", pct: ev.pct, message: ev.message });
      } else if (ev.type === "done") {
        es.close();
        activeEs = null;
        dispatch({ type: "SUCCESS", session: ev.result as never });
      } else if (ev.type === "error") {
        es.close();
        activeEs = null;
        dispatch({
          type: "ERROR",
          error: new Error(ev.message),
          errorCode: ev.code,
        });
      }
    };

    es.onerror = () => {
      es.close();
      activeEs = null;
      // 연결 끊김 — GET /v1/sessions/{id} 폴백
      getSession(sessionId)
        .then((session) => {
          dispatch({ type: "SUCCESS", session });
        })
        .catch((err) => {
          const error = err instanceof Error ? err : new Error(String(err));
          dispatch({ type: "ERROR", error, errorCode: extractErrorCode(err) });
        });
    };
  }

  async function submit(values: UploadFormValues) {
    dispatch({ type: "SUBMIT", isCustomEvent: values.event_type_is_custom });
    navigate("/analyzing");

    try {
      const { session_id } = await createSession(values);
      subscribeToStream(session_id);
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      const errorCode = extractErrorCode(err);
      dispatch({ type: "ERROR", error, errorCode });
    }
  }

  function reset() {
    if (activeEs) {
      activeEs.close();
      activeEs = null;
    }
    dispatch({ type: "RESET" });
    navigate("/");
  }

  return { submit, reset };
}
