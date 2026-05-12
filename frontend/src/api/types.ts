import type { CreateSessionResponse, SessionResponse, SimulateResponse, UploadFormValues } from "./schemas";

export interface ApiAdapter {
  createSession(form: UploadFormValues): Promise<CreateSessionResponse>;
  getSession(sessionId: string): Promise<SessionResponse>;
  simulate(sessionId: string, appliedSuggestionIds: string[]): Promise<SimulateResponse>;
}
