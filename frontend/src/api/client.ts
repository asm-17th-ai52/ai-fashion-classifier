import { apiAdapter } from "./adapter";
import type { UploadFormValues, SessionResponse, SimulateResponse } from "./schemas";

export function createSession(form: UploadFormValues): Promise<SessionResponse> {
  return apiAdapter.createSession(form);
}

export function simulate(
  sessionId: string,
  appliedSuggestionIds: string[]
): Promise<SimulateResponse> {
  return apiAdapter.simulate(sessionId, appliedSuggestionIds);
}
