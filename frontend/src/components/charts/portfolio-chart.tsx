"use client";

import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { chartTokens, EChart } from "@/components/charts/echart";

/*
  PortfolioChart — the shared portfolio time-series used by the dashboard and
  the performance page, so the same data always renders with the same colors
  (UI_SYSTEM chart rules). Presentation only; each caller fetches its points.
  Deposits (▲) / withdrawals (▼) are marked so external flows are never
  mistaken for performance.
*/

export interface CurvePoint {
  date: string;
  nav: number;
  cum_return: number;
  drawdown: number;
  flow: number;
}

export type ChartMode = "nav" | "return" | "drawdown";

export function PortfolioChart({
  points,
  mode,
  height = 300,
  currency = "USD",
}: {
  points: CurvePoint[];
  mode: ChartMode;
  height?: number;
  currency?: string;
}) {
  const option = useMemo<EChartsOption>(() => {
    const t = chartTokens();
    const dates = points.map((p) => p.date);
    const flowMarkers = points
      .filter((p) => p.flow !== 0)
      .map((p) => ({
        coord: [p.date, mode === "nav" ? p.nav : mode === "return" ? p.cum_return * 100 : 0] as [
          string,
          number,
        ],
        value: p.flow > 0 ? "▲" : "▼",
      }));

    const series =
      mode === "nav"
        ? points.map((p) => p.nav)
        : mode === "return"
          ? points.map((p) => +(p.cum_return * 100).toFixed(4))
          : points.map((p) => +(p.drawdown * 100).toFixed(4));

    const color = mode === "drawdown" ? t.loss : t.accent;

    return {
      backgroundColor: "transparent",
      grid: { left: 8, right: 12, top: 14, bottom: 44, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: t.panel,
        borderColor: t.line,
        textStyle: { color: t.fg, fontSize: 11 },
        valueFormatter: (v) =>
          mode === "nav"
            ? `${Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 })} ${currency}`
            : `${Number(v).toFixed(2)}%`,
      },
      xAxis: {
        type: "category",
        data: dates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: t.line } },
        axisLabel: { color: t.faint, fontSize: 10, hideOverlap: true },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        scale: mode === "nav",
        splitLine: { lineStyle: { color: t.line, opacity: 0.55 } },
        axisLabel: {
          color: t.faint,
          fontSize: 10,
          formatter: (v: number) => (mode === "nav" ? v.toLocaleString("en-US") : `${v}%`),
        },
      },
      dataZoom: [
        { type: "inside", throttle: 60 },
        {
          type: "slider",
          height: 16,
          bottom: 8,
          borderColor: t.line,
          fillerColor: t.accentSoft,
          handleStyle: { color: t.accent },
          textStyle: { color: t.faint, fontSize: 9 },
        },
      ],
      series: [
        {
          type: "line",
          data: series,
          showSymbol: false,
          smooth: false,
          lineStyle: { width: 2, color },
          areaStyle: { color, opacity: mode === "drawdown" ? 0.12 : 0.07 },
          markPoint: {
            symbol: "circle",
            symbolSize: 1,
            label: { show: true, fontSize: 11, color: t.fg },
            data: flowMarkers,
          },
        },
      ],
    } as EChartsOption;
  }, [points, mode, currency]);

  return <EChart option={option} height={height} />;
}
