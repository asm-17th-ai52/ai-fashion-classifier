import { useState } from "react";
import { simulate } from "@/api/client";
import { useSessionState, useSessionDispatch } from "@/store/sessionContext";

export function useSimulation() {
  const state = useSessionState();
  const dispatch = useSessionDispatch();
  const [pending, setPending] = useState(false);
  const [activeSuggestionIds, setActiveSuggestionIds] = useState<string[]>([]);

  const sessionId = state.status === "success" ? state.session.session_id : null;

  async function toggle(suggestionId: string) {
    if (!sessionId) return;

    const next = activeSuggestionIds.includes(suggestionId)
      ? activeSuggestionIds.filter((id) => id !== suggestionId)
      : [...activeSuggestionIds, suggestionId];

    setActiveSuggestionIds(next);
    if (next.length === 0) {
      dispatch({ type: "SIMULATE_SUCCESS", simulation: null });
      return;
    }

    setPending(true);
    try {
      const result = await simulate(sessionId, next);
      dispatch({ type: "SIMULATE_SUCCESS", simulation: result });
    } finally {
      setPending(false);
    }
  }

  function clear() {
    setActiveSuggestionIds([]);
    dispatch({ type: "SIMULATE_SUCCESS", simulation: null });
  }

  return { pending, activeSuggestionIds, toggle, clear };
}
