import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ScoreGauge from "./ScoreGauge";

describe("ScoreGauge", () => {
  it("displays the score", () => {
    render(<ScoreGauge score={62} capApplied={null} />);
    expect(screen.getByText("62")).toBeInTheDocument();
  });

  it("shows 낮음 label for score < 30", () => {
    render(<ScoreGauge score={20} capApplied={null} />);
    expect(screen.getByText("낮음")).toBeInTheDocument();
  });

  it("shows 주의 label for 30 ≤ score < 60", () => {
    render(<ScoreGauge score={45} capApplied={null} />);
    expect(screen.getByText("주의")).toBeInTheDocument();
  });

  it("shows 적합 label for 60 ≤ score < 80", () => {
    render(<ScoreGauge score={69} capApplied={null} />);
    expect(screen.getByText("적합")).toBeInTheDocument();
  });

  it("shows 매우 적합 label for score ≥ 80", () => {
    render(<ScoreGauge score={85} capApplied={null} />);
    expect(screen.getByText("매우 적합")).toBeInTheDocument();
  });

  it('shows "핵심 미스 캡" badge when cap_applied is blocker_cap_50', () => {
    render(<ScoreGauge score={45} capApplied="blocker_cap_50" />);
    expect(screen.getByText("핵심 미스 캡")).toBeInTheDocument();
  });

  it("does not show badge when cap_applied is null", () => {
    render(<ScoreGauge score={70} capApplied={null} />);
    expect(screen.queryByText("핵심 미스 캡")).not.toBeInTheDocument();
  });

  it("shows simulated score and delta when simulatedScore is provided", () => {
    render(<ScoreGauge score={62} capApplied={null} simulatedScore={79} />);
    expect(screen.getByText("79")).toBeInTheDocument();
    expect(screen.getByText("+17 sim")).toBeInTheDocument();
  });

  it("has aria-label on score SVG", () => {
    render(<ScoreGauge score={62} capApplied={null} />);
    expect(screen.getByLabelText("종합 점수 62점")).toBeInTheDocument();
  });
});
