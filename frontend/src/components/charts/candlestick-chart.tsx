"use client";

import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { chartTokens, EChart } from "@/components/charts/echart";

/*
  CandlestickChart — the Legend centerpiece: daily OHLC candles (green up / red
  down) with MA7 + MA25 overlays and a volume band beneath. Presentation only;
  the caller supplies real bars from the price-history endpoint. Renders LTR
  (time reads left→right) inside the RTL page.
*/

export interface Bar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= period) sum -= values[i - period];
    out.push(i >= period - 1 ? +(sum / period).toFixed(4) : null);
  }
  return out;
}

export function CandlestickChart({
  bars,
  height = 320,
}: {
  bars: Bar[];
  height?: number;
}) {
  const option = useMemo<EChartsOption>(() => {
    const t = chartTokens();
    const dates = bars.map((b) => b.date);
    // ECharts candlestick datum = [open, close, low, high]
    const ohlc = bars.map((b) => [b.open, b.close, b.low, b.high]);
    const closes = bars.map((b) => b.close);
    const ma7 = sma(closes, 7);
    const ma25 = sma(closes, 25);
    const volumes = bars.map((b, i) => ({
      value: b.volume,
      itemStyle: { color: b.close >= b.open ? t.gainDim : t.lossDim },
      _i: i,
    }));

    return {
      backgroundColor: "transparent",
      animation: false,
      axisPointer: { link: [{ xAxisIndex: "all" }], label: { backgroundColor: t.faint } },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        backgroundColor: t.panel,
        borderColor: t.line,
        textStyle: { color: t.fg, fontSize: 11 },
      },
      grid: [
        { left: 8, right: 54, top: 12, height: "62%", containLabel: false },
        { left: 8, right: 54, top: "76%", height: "16%", containLabel: false },
      ],
      xAxis: [
        {
          type: "category",
          data: dates,
          gridIndex: 0,
          boundaryGap: true,
          axisLine: { lineStyle: { color: t.line } },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        {
          type: "category",
          data: dates,
          gridIndex: 1,
          boundaryGap: true,
          axisLine: { lineStyle: { color: t.line } },
          axisTick: { show: false },
          axisLabel: { color: t.faint, fontSize: 10, hideOverlap: true },
          splitLine: { show: false },
        },
      ],
      yAxis: [
        {
          scale: true,
          position: "right",
          gridIndex: 0,
          splitLine: { lineStyle: { color: t.line, opacity: 0.5 } },
          axisLine: { show: false },
          axisLabel: { color: t.faint, fontSize: 10, formatter: (v: number) => v.toFixed(0) },
        },
        {
          gridIndex: 1,
          position: "right",
          splitLine: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
        },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1], throttle: 60 },
        {
          type: "slider",
          xAxisIndex: [0, 1],
          height: 14,
          bottom: 2,
          borderColor: t.line,
          fillerColor: t.accentSoft,
          handleStyle: { color: t.accent },
          textStyle: { color: t.faint, fontSize: 9 },
        },
      ],
      series: [
        {
          type: "candlestick",
          data: ohlc,
          xAxisIndex: 0,
          yAxisIndex: 0,
          barMaxWidth: 12,
          itemStyle: {
            color: t.gain,
            color0: t.loss,
            borderColor: t.gain,
            borderColor0: t.loss,
          },
        },
        {
          type: "line",
          name: "MA7",
          data: ma7,
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.4, color: t.warn, opacity: 0.9 },
        },
        {
          type: "line",
          name: "MA25",
          data: ma25,
          xAxisIndex: 0,
          yAxisIndex: 0,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 1.4, color: t.info, opacity: 0.9 },
        },
        {
          type: "bar",
          name: "נפח",
          data: volumes,
          xAxisIndex: 1,
          yAxisIndex: 1,
          barMaxWidth: 12,
        },
      ],
    } as EChartsOption;
  }, [bars]);

  return <EChart option={option} height={height} />;
}
