export function scoreColor(score: number): string {
  if (score < 30) return "text-score-low";
  if (score < 60) return "text-score-mid";
  if (score < 80) return "text-score-good";
  return "text-score-high";
}

export function scoreBarColor(score: number): string {
  if (score < 30) return "bg-score-low";
  if (score < 60) return "bg-score-mid";
  if (score < 80) return "bg-score-good";
  return "bg-score-high";
}

export function passRateLabel(passed: number, applicable: number): string {
  return `${passed}/${applicable}`;
}

export function formatDelta(delta: number): string {
  return delta >= 0 ? `+${delta}점` : `${delta}점`;
}
