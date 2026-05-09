import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import SuggestionCard from "./SuggestionCard";
import type { Suggestion, Check } from "@/api/schemas";

const suggestion: Suggestion = {
  id: "sg_1",
  fixes_check_ids: ["A1"],
  action: { type: "swap", target_slot: "shoes", from: "로퍼", to: "옥스퍼드" },
  rationale_facts: ["옥스퍼드는 business_meeting 기대 범위"],
  expected_overall_delta: 10,
  removes_blocker: false,
  user_facing_text: "신발을 옥스퍼드로 교체하세요.",
};

const checksById = new Map<string, Check>([
  [
    "A1",
    {
      id: "A1",
      group: "dresscode",
      label: "신발 카테고리가 기대 범위에 포함",
      result: "fail",
      applicable: true,
      is_blocker: false,
      evidence_facts: [],
    },
  ],
]);

describe("SuggestionCard", () => {
  it("renders user_facing_text", () => {
    render(
      <SuggestionCard
        suggestion={suggestion}
        checksById={checksById}
        isActive={false}
        onToggle={() => {}}
        simulationPending={false}
      />
    );
    expect(screen.getByText("신발을 옥스퍼드로 교체하세요.")).toBeInTheDocument();
  });

  it("renders expected delta", () => {
    render(
      <SuggestionCard
        suggestion={suggestion}
        checksById={checksById}
        isActive={false}
        onToggle={() => {}}
        simulationPending={false}
      />
    );
    expect(screen.getByText("+10점")).toBeInTheDocument();
  });

  it("renders fixes check id", () => {
    render(
      <SuggestionCard
        suggestion={suggestion}
        checksById={checksById}
        isActive={false}
        onToggle={() => {}}
        simulationPending={false}
      />
    );
    // New design shows check ID ("A1") with full label as title attribute
    expect(screen.getByText("A1")).toBeInTheDocument();
  });

  it("calls onToggle when simulation button clicked", () => {
    const onToggle = vi.fn();
    render(
      <SuggestionCard
        suggestion={suggestion}
        checksById={checksById}
        isActive={false}
        onToggle={onToggle}
        simulationPending={false}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /simul/i }));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("shows active state when isActive=true", () => {
    render(
      <SuggestionCard
        suggestion={suggestion}
        checksById={checksById}
        isActive={true}
        onToggle={() => {}}
        simulationPending={false}
      />
    );
    const btn = screen.getByRole("button", { name: /simul/i });
    expect(btn).toHaveAttribute("aria-pressed", "true");
    expect(btn.className).toContain("bg-accent-blue");
  });

  it("shows blocker emphasis when removes_blocker=true", () => {
    const blockerSuggestion = { ...suggestion, removes_blocker: true };
    render(
      <SuggestionCard
        suggestion={blockerSuggestion}
        checksById={checksById}
        isActive={false}
        onToggle={() => {}}
        simulationPending={false}
      />
    );
    expect(screen.getByText("blocker fix")).toBeInTheDocument();
    const article = screen.getByRole("article");
    expect(article.className).toContain("border-accent-red");
  });
});
