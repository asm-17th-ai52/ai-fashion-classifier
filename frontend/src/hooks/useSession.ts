import { useNavigate } from "react-router-dom";
import { createSession } from "@/api/client";
import { useSessionDispatch } from "@/store/sessionContext";
import type { UploadFormValues } from "@/api/schemas";

function extractErrorCode(err: unknown): string | undefined {
  if (err && typeof err === "object" && "body" in err) {
    const body = (err as { body?: { error?: { code?: string } } }).body;
    return body?.error?.code;
  }
  return undefined;
}

export function useSession() {
  const dispatch = useSessionDispatch();
  const navigate = useNavigate();

  async function submit(values: UploadFormValues) {
    dispatch({ type: "SUBMIT", isCustomEvent: values.event_type_is_custom });
    navigate("/analyzing");

    try {
      const session = await createSession(values);
      dispatch({ type: "SUCCESS", session });
      navigate("/result");
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      const errorCode = extractErrorCode(err);
      dispatch({ type: "ERROR", error, errorCode });
    }
  }

  function reset() {
    dispatch({ type: "RESET" });
    navigate("/");
  }

  return { submit, reset };
}
