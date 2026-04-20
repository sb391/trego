export function formatNumber(value?: number | null, maximumFractionDigits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits }).format(value);
}

export function formatCurrencyCr(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${formatNumber(value)} Cr`;
}

export function formatPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${formatNumber(value)}%`;
}

export function formatDateLabel(value?: string | null): string {
  if (!value) {
    return "—";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
}

export function riskToneClass(tone?: string | null): string {
  switch ((tone || "").toLowerCase()) {
    case "high":
      return "tone-high";
    case "medium":
      return "tone-medium";
    case "low":
      return "tone-low";
    default:
      return "tone-neutral";
  }
}

export function listedLabel(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "Unknown";
}
