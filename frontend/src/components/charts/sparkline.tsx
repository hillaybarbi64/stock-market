"use client";

import { useId } from "react";

/*
  Sparkline — a tiny inline SVG trend, cheap enough to render many per screen
  (watchlists, table rows). No axes, no labels. Tone defaults to the sign of
  (last − first): gains draw green, losses red. Always LTR (time reads L→R).
*/
export function Sparkline({
  data,
  width = 120,
  height = 26,
  tone = "auto",
  strokeWidth = 1.3,
  fill = true,
  className = "",
}: {
  data: number[];
  width?: number;
  height?: number;
  tone?: "auto" | "gain" | "loss" | "accent";
  strokeWidth?: number;
  fill?: boolean;
  className?: string;
}) {
  const id = useId();
  if (!data || data.length < 2) {
    return <svg viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden />;
  }
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pad = 2;
  const x = (i: number) => pad + (width - 2 * pad) * (i / (data.length - 1));
  const y = (v: number) => pad + (height - 2 * pad) * (1 - (v - min) / span);

  const color =
    tone === "gain"
      ? "var(--gain)"
      : tone === "loss"
        ? "var(--loss)"
        : tone === "accent"
          ? "var(--accent)"
          : data[data.length - 1] >= data[0]
            ? "var(--gain)"
            : "var(--loss)";

  const line = data.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area =
    `M${x(0).toFixed(1)},${y(data[0]).toFixed(1)} ` +
    data.map((v, i) => `L${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ") +
    ` L${x(data.length - 1).toFixed(1)},${height} L0,${height} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      preserveAspectRatio="none"
      aria-hidden
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.22" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {fill && <path d={area} fill={`url(#${id})`} />}
      <polyline
        points={line}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
