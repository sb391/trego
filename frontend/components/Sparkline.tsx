"use client";

import { TrendPoint } from "../lib/types";

type Props = {
  points: TrendPoint[];
  stroke?: string;
  title?: string;
};

export function Sparkline({ points, stroke = "#c7a34b", title }: Props) {
  const valid = points.filter((point) => typeof point.value === "number") as Array<{ label: string; value: number }>;
  if (valid.length < 2) {
    return <div className="sparkline-empty">{title ? `${title}: no trend available` : "No trend available"}</div>;
  }

  const width = 220;
  const height = 72;
  const padding = 8;
  const values = valid.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const step = (width - padding * 2) / (valid.length - 1);
  const coordinates = valid.map((point, index) => {
    const x = padding + index * step;
    const y = height - padding - ((point.value - min) / span) * (height - padding * 2);
    return { ...point, x, y };
  });
  const path = coordinates.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const latest = coordinates[coordinates.length - 1];

  return (
    <div className="sparkline-card">
      {title ? <div className="sparkline-title">{title}</div> : null}
      <svg viewBox={`0 0 ${width} ${height}`} className="sparkline-svg" role="img" aria-label={title ?? "trend chart"}>
        <path d={path} fill="none" stroke={stroke} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={latest.x} cy={latest.y} r="4" fill={stroke} />
      </svg>
      <div className="sparkline-labels">
        <span>{valid[0].label}</span>
        <span>{latest.label}</span>
      </div>
    </div>
  );
}
