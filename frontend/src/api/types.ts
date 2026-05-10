import type { CreateSessionResponse, SessionResponse, SimulateResponse, UploadFormValues } from "./schemas";

export interface StreamCallbacks {
  onProgress: (pct: number, message: string) => void;
  onDone: (session: SessionResponse) => void;
  onError: (error: Error, errorCode?: string) => void;
}

export interface ApiAdapter {
  createSession(form: UploadFormValues): Promise<CreateSessionResponse>;
  /** Opens a stream subscription. Returns a cleanup function that closes it. */
  subscribeStream(sessionId: string, callbacks: StreamCallbacks): () => void;
  getSession(sessionId: string): Promise<SessionResponse>;
  simulate(sessionId: string, appliedSuggestionIds: string[]): Promise<SimulateResponse>;
}
