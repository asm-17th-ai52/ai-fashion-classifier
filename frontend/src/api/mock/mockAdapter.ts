import type { ApiAdapter, StreamCallbacks } from "../types";
import type { UploadFormValues, CreateSessionResponse, SessionResponse, SimulateResponse } from "../schemas";
import { MOCK_SESSION, computeSimulation } from "./fixtures";

const MOCK_SESSION_ID = "mock-session-001";

function delay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

const MOCK_STREAM_STEPS: { pct: number; message: string }[] = [
  { pct: 8,  message: "[VISION] 이미지 전처리 완료" },
  { pct: 18, message: "[VISION] 상의 감지: 드레스 셔츠 (confidence 0.92)" },
  { pct: 28, message: "[VISION] 하의 감지: 치노 팬츠 (confidence 0.88)" },
  { pct: 35, message: "[VISION] 신발 감지: 로퍼 (confidence 0.85)" },
  { pct: 48, message: "[CONTEXT] 드레스코드 규칙 조회 중 — business_meeting" },
  { pct: 62, message: "[CONTEXT] tier1 RAG 매칭 완료 (score 0.91)" },
  { pct: 72, message: "[RECOMMEND] 14개 체크 항목 평가 중..." },
  { pct: 83, message: "[RECOMMEND] A1 fail · A3 fail · B2 fail · C2 fail" },
  { pct: 92, message: "[NARRATOR] 종합 평가 문장 생성 중..." },
  { pct: 98, message: "[NARRATOR] 개선 제안 2건 생성 완료" },
];

export class MockApiAdapter implements ApiAdapter {
  async createSession(_form: UploadFormValues): Promise<CreateSessionResponse> {
    await delay(300);
    return { session_id: MOCK_SESSION_ID };
  }

  subscribeStream(_sessionId: string, callbacks: StreamCallbacks): () => void {
    let cancelled = false;

    (async () => {
      for (const step of MOCK_STREAM_STEPS) {
        if (cancelled) return;
        await delay(420);
        if (cancelled) return;
        callbacks.onProgress(step.pct, step.message);
      }
      if (cancelled) return;
      await delay(420);
      if (cancelled) return;
      callbacks.onDone(structuredClone(MOCK_SESSION));
    })();

    return () => { cancelled = true; };
  }

  async getSession(_sessionId: string): Promise<SessionResponse> {
    await delay(300);
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
