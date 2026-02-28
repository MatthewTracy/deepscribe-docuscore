export function formatNumber(value: number, decimals = 1): string {
  return value.toFixed(decimals);
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function gateColor(
  decision: "PASS" | "REVIEW" | "FAIL"
): string {
  switch (decision) {
    case "PASS":
      return "bg-gate-pass/20 text-gate-pass border-gate-pass/30";
    case "REVIEW":
      return "bg-gate-review/20 text-gate-review border-gate-review/30";
    case "FAIL":
      return "bg-gate-fail/20 text-gate-fail border-gate-fail/30";
  }
}

export function severityColor(
  severity: "critical" | "major" | "minor"
): string {
  switch (severity) {
    case "critical":
      return "bg-severity-critical/20 text-severity-critical border-severity-critical/30";
    case "major":
      return "bg-severity-major/20 text-severity-major border-severity-major/30";
    case "minor":
      return "bg-severity-minor/20 text-severity-minor border-severity-minor/30";
  }
}

export function scoreBarWidth(score: number, max = 1): string {
  return `${(score / max) * 100}%`;
}

export function scoreBarColor(score: number): string {
  if (score >= 0.8) return "bg-gate-pass";
  if (score >= 0.6) return "bg-gate-review";
  return "bg-gate-fail";
}

// For section scores (1-5 scale from LLM judge)
export function sectionScoreBarColor(score: number): string {
  if (score >= 4) return "bg-gate-pass";
  if (score >= 3) return "bg-gate-review";
  return "bg-gate-fail";
}

export function classNames(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// Fix UTF-8 mojibake from the source dataset (e.g. Ã— → ×)
export function sanitizeText(text: string): string {
  return text
    .replace(/Ã—/g, "×")
    .replace(/Ã©/g, "é")
    .replace(/Ã¨/g, "è")
    .replace(/Ã¼/g, "ü")
    .replace(/Ã¶/g, "ö")
    .replace(/Ã¤/g, "ä");
}
