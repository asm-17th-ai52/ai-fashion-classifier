import { describe, it, expect } from "vitest";
import { scoreColor, scoreBarColor, formatDelta, passRateLabel } from "./format";

describe("scoreColor", () => {
  it("returns score-low for score < 30", () => {
    expect(scoreColor(0)).toBe("text-score-low");
    expect(scoreColor(29)).toBe("text-score-low");
  });

  it("returns score-mid for 30 ≤ score < 60", () => {
    expect(scoreColor(30)).toBe("text-score-mid");
    expect(scoreColor(59)).toBe("text-score-mid");
  });

  it("returns score-good for 60 ≤ score < 80", () => {
    expect(scoreColor(60)).toBe("text-score-good");
    expect(scoreColor(79)).toBe("text-score-good");
  });

  it("returns score-high for score ≥ 80", () => {
    expect(scoreColor(80)).toBe("text-score-high");
    expect(scoreColor(100)).toBe("text-score-high");
  });
});

describe("scoreBarColor", () => {
  it("mirrors scoreColor with bg- prefix", () => {
    expect(scoreBarColor(20)).toBe("bg-score-low");
    expect(scoreBarColor(50)).toBe("bg-score-mid");
    expect(scoreBarColor(70)).toBe("bg-score-good");
    expect(scoreBarColor(90)).toBe("bg-score-high");
  });
});

describe("formatDelta", () => {
  it("prefixes + for positive", () => {
    expect(formatDelta(10)).toBe("+10점");
    expect(formatDelta(0)).toBe("+0점");
  });

  it("keeps minus for negative", () => {
    expect(formatDelta(-5)).toBe("-5점");
  });
});

describe("passRateLabel", () => {
  it("formats as X/Y", () => {
    expect(passRateLabel(3, 5)).toBe("3/5");
    expect(passRateLabel(0, 6)).toBe("0/6");
  });
});
