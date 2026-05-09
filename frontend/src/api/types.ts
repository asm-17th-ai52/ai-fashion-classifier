import type { SessionResponse, SimulateResponse, UploadFormValues } from "./schemas";

export interface ApiAdapter {
  createSession(form: UploadFormValues): Promise<SessionResponse>;
  simulate(sessionId: string, appliedSuggestionIds: string[]): Promise<SimulateResponse>;
}
