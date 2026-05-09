import type { ApiAdapter } from "../types";
import type { UploadFormValues, SessionResponse, SimulateResponse } from "../schemas";
import { MOCK_SESSION, computeSimulation } from "./fixtures";

const MOCK_DELAY_MS = 1800;

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

export class MockApiAdapter implements ApiAdapter {
  async createSession(_form: UploadFormValues): Promise<SessionResponse> {
    await delay(MOCK_DELAY_MS);
    return structuredClone(MOCK_SESSION);
  }

  async simulate(
    sessionId: string,
    appliedSuggestionIds: string[]
  ): Promise<SimulateResponse> {
    await delay(300);
    return computeSimulation(sessionId, appliedSuggestionIds);
  }
}
