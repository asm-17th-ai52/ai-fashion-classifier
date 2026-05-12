import type { ApiAdapter } from "./types";
import { MockApiAdapter } from "./mock/mockAdapter";
import { HttpApiAdapter } from "./http/httpAdapter";

// ← 이 값 하나로 mock ↔ 실제 API 전환
// .env: VITE_API_ADAPTER=mock | http
export const apiAdapter: ApiAdapter =
  import.meta.env.VITE_API_ADAPTER === "mock"
    ? new MockApiAdapter()
    : new HttpApiAdapter();
