"use client";

import type { EChartsOption } from "echarts";
import * as echarts from "echarts";
import { useEffect, useRef } from "react";

/*
  Thin ECharts wrapper: init once, update options, resize with the container,
  re-render on theme flips (data-theme on <html>). Charts render LTR
  internally (time axes read left→right) inside the RTL page.
*/
export function EChart({
  option,
  height = 320,
  onReady,
}: {
  option: EChartsOption;
  height?: number;
  onReady?: (chart: echarts.ECharts) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chartRef.current = chart;
    onReady?.(chart);

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current);

    const mo = new MutationObserver(() => {
      // theme change → caller passes CSS-var-derived colors, so just refresh
      chart.setOption(withAnimation(option), { notMerge: false });
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

    return () => {
      ro.disconnect();
      mo.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(withAnimation(option), { notMerge: true });
  }, [option]);

  return <div ref={ref} style={{ height }} dir="ltr" />;
}

/*
  Calm native draw aligned to our motion scale: 480ms first paint (2x --dur-slow,
  justified for a first paint), 240ms tweened updates (= --dur-slow), cubicOut to
  match the --ease decelerate feel. This is the one motion the CSS reduced-motion
  floor cannot reach (canvas/JS), so we gate it on matchMedia and disable tweening
  entirely under reduced motion.
*/
function withAnimation(option: EChartsOption): EChartsOption {
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return {
    ...option,
    animation: !reduced,
    animationDuration: 480,
    animationEasing: "cubicOut",
    animationDurationUpdate: 240,
    animationEasingUpdate: "cubicOut",
  };
}

const CAT_FALLBACK = [
  "#00d47e", "#4c9ffe", "#e7b24a", "#a97bd6",
  "#ff7a66", "#4fd0c9", "#b6c24d", "#ff7fb0",
];

/** Turn a #rrggbb into an rgba() string with the given alpha (for canvas fills
    that can't parse color-mix). Falls back to the input if it's not hex. */
function rgba(hex: string, alpha: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

/** Read the current values of our design tokens for chart styling. */
export function chartTokens() {
  if (typeof window === "undefined") {
    return {
      fg: "#8b93a1",
      faint: "#565d69",
      line: "#1e2129",
      accent: "#00d47e",
      accentSoft: "rgba(0,212,126,0.15)",
      gain: "#00d47e",
      gainDim: "rgba(0,212,126,0.22)",
      loss: "#ff4d5e",
      lossDim: "rgba(255,77,94,0.22)",
      warn: "#e7b24a",
      info: "#4c9ffe",
      panel: "#111318",
      cat: CAT_FALLBACK,
    };
  }
  const css = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  const gain = v("--gain", "#00d47e");
  const loss = v("--loss", "#ff4d5e");
  return {
    fg: v("--fg-muted", "#8b93a1"),
    faint: v("--fg-faint", "#565d69"),
    line: v("--border", "#1e2129"),
    accent: v("--accent", "#00d47e"),
    accentSoft: v("--accent-soft", "rgba(0,212,126,0.15)"),
    gain,
    gainDim: rgba(gain, 0.22),
    loss,
    lossDim: rgba(loss, 0.22),
    warn: v("--warn", "#e7b24a"),
    info: v("--info", "#4c9ffe"),
    panel: v("--bg-panel", "#111318"),
    cat: CAT_FALLBACK.map((fb, i) => v(`--cat-${i + 1}`, fb)),
  };
}
