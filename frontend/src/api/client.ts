import { apiAdapter } from "./adapter";
import type { UploadFormValues, CreateSessionResponse, SessionResponse, SimulateResponse } from "./schemas";

export function createSession(form: UploadFormValues): Promise<CreateSessionResponse> {
  return apiAdapter.createSession(form);
}

export function getSession(sessionId: string): Promise<SessionResponse> {
  return apiAdapter.getSession(sessionId);
}

export function simulate(
  sessionId: string,
  appliedSuggestionIds: string[]
): Promise<SimulateResponse> {
  return apiAdapter.simulate(sessionId, appliedSuggestionIds);
}
