import { createContext, useContext, useReducer } from "react";
import type { Dispatch, ReactNode } from "react";
import type { SessionResponse, SimulateResponse } from "@/api/schemas";

export type SessionState =
  | { status: "idle" }
  | { status: "loading"; isCustomEvent: boolean; progress: number; agentProgress: Record<string, number>; logs: { pct: number; message: string; agent: string }[] }
  | { status: "success"; session: SessionResponse; simulation: SimulateResponse | null }
  | { status: "error"; error: Error; errorCode?: string };

type SessionAction =
  | { type: "SUBMIT"; isCustomEvent: boolean }
  | { type: "PROGRESS"; pct: number; agentPct: number; message: string; agent: string }
  | { type: "SUCCESS"; session: SessionResponse }
  | { type: "ERROR"; error: Error; errorCode?: string }
  | { type: "SIMULATE_SUCCESS"; simulation: SimulateResponse | null }
  | { type: "RESET" };

function reducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "SUBMIT":
      return { status: "loading", isCustomEvent: action.isCustomEvent, progress: 0, agentProgress: {}, logs: [] };
    case "PROGRESS":
      if (state.status !== "loading") return state;
      return {
        ...state,
        progress: Math.max(state.progress, action.pct),
        agentProgress: {
          ...state.agentProgress,
          [action.agent]: Math.max(state.agentProgress[action.agent] ?? 0, action.agentPct),
        },
        logs: [...state.logs, { pct: action.pct, message: action.message, agent: action.agent }],
      };
    case "SUCCESS":
      return { status: "success", session: action.session, simulation: null };
    case "ERROR":
      return { status: "error", error: action.error, errorCode: action.errorCode };
    case "SIMULATE_SUCCESS":
      if (state.status !== "success") return state;
      return { ...state, simulation: action.simulation };
    case "RESET":
      return { status: "idle" };
  }
}

const StateContext = createContext<SessionState | null>(null);
const DispatchContext = createContext<Dispatch<SessionAction> | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, { status: "idle" });
  return (
    <StateContext.Provider value={state}>
      <DispatchContext.Provider value={dispatch}>
        {children}
      </DispatchContext.Provider>
    </StateContext.Provider>
  );
}

export function useSessionState(): SessionState {
  const ctx = useContext(StateContext);
  if (!ctx) throw new Error("useSessionState must be inside SessionProvider");
  return ctx;
}

export function useSessionDispatch(): Dispatch<SessionAction> {
  const ctx = useContext(DispatchContext);
  if (!ctx) throw new Error("useSessionDispatch must be inside SessionProvider");
  return ctx;
}
