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
      chart.setOption(option, { notMerge: false });
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
    chartRef.current?.setOption(option, { notMerge: true });
  }, [option]);

  return <div ref={ref} style={{ height }} dir="ltr" />;
}

/** Read the current values of our design tokens for chart styling. */
export function chartTokens() {
  if (typeof window === "undefined") {
    return {
      fg: "#a0a4b4",
      faint: "#6d7182",
      line: "#2c2f3a",
      accent: "#6c93f0",
      gain: "#3fb884",
      loss: "#e06470",
      panel: "#1a1c23",
    };
  }
  const css = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    fg: v("--fg-muted", "#a0a4b4"),
    faint: v("--fg-faint", "#6d7182"),
    line: v("--border", "#2c2f3a"),
    accent: v("--accent", "#6c93f0"),
    gain: v("--gain", "#3fb884"),
    loss: v("--loss", "#e06470"),
    panel: v("--bg-panel", "#1a1c23"),
  };
}
