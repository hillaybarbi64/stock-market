"use client";

import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import { chartTokens, EChart } from "@/components/charts/echart";
import { Panel } from "@/components/ui/panel";
import { StatRail, StatCell } from "@/components/ui/stat-rail";
import { Num } from "@/components/ui/num";
import { Tabs } from "@/components/ui/tabs";
import { apiGet } from "@/lib/api";

interface Gated {
  value: number | null;
  sufficient: boolean;
  available: number;
  required: number;
  note?: string | null;
}

interface Summary {
  available: boolean;
  detail?: string;
  as_of?: string;
  since?: string;
  days_available: number;
  returns?: {
    total_twr: number;
    day: number | null;
    wtd: number | null;
    mtd: number | null;
    ytd: number | null;
    one_year: number | null;
    annualized: Gated;
    xirr: number | null;
  };
  risk?: {
    max_drawdown: number;
    max_drawdown_date: string | null;
    current_drawdown: number;
    recovery_days: number | null;
    volatility: Gated;
    sharpe: Gated;
    sortino: Gated;
  };
  cash?: {
    deposits: number;
    withdrawals: number;
    dividends: number;
    withholding_tax: number;
    fees: number;
    interest_net: number;
  };
}

interface CurvePoint {
  date: string;
  nav: number;
  cum_return: number;
  drawdown: number;
  flow: number;
}

type ChartMode = "nav" | "return" | "drawdown";

const CHART_MODES = [
  { value: "nav" as const, label: "שווי" },
  { value: "return" as const, label: "תשואה %" },
  { value: "drawdown" as const, label: "Drawdown" },
];

/** Render a gated metric: the value if there's enough history, else a compact
    "insufficient data" note with the available/required day count. */
function gated(g: Gated | undefined, asPct: boolean) {
  if (g?.sufficient) {
    return asPct ? <Num value={g.value} asPct /> : <span className="num">{g.value?.toFixed(2)}</span>;
  }
  return (
    <span className="text-[11px] font-normal leading-snug text-faint">
      חסרים נתונים · <span className="num">{g ? `${g.available}/${g.required}` : "—"}</span>
    </span>
  );
}

export default function PerformancePage() {
  const summary = useQuery({
    queryKey: ["performance", "summary"],
    queryFn: () => apiGet<Summary>("/performance/summary"),
  });
  const curve = useQuery({
    queryKey: ["performance", "curve"],
    queryFn: () => apiGet<{ available: boolean; points: CurvePoint[] }>("/performance/equity-curve"),
  });
  const monthly = useQuery({
    queryKey: ["performance", "monthly"],
    queryFn: () => apiGet<{ available: boolean; months: Record<string, number> }>("/performance/monthly"),
  });
  const [mode, setMode] = useState<ChartMode>("nav");

  const s = summary.data;

  if (s && !s.available) {
    return (
      <div className="mx-auto max-w-5xl space-y-4">
        <h1 className="text-[17px] font-semibold tracking-tight">ביצועים</h1>
        <Panel>
          <div className="py-10 text-center">
            <p className="text-[13.5px] font-medium">אין עדיין היסטוריה לחישוב</p>
            <p className="mx-auto mt-1 max-w-md text-[12.5px] text-muted">{s.detail}</p>
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h1 className="t-h1">ביצועים</h1>
        {s?.as_of && (
          <span className="num text-[11px] text-faint" dir="ltr">
            {s.since} → {s.as_of} · {s.days_available}d
          </span>
        )}
      </div>

      {/* ── KPI rail: time-weighted returns ─────────────────────────── */}
      <Panel title="תשואות" subtitle="Time-Weighted" padding="none" actions={<span className="tag">TWR</span>}>
        <StatRail cols="grid-cols-2 sm:grid-cols-4 lg:grid-cols-7">
          <StatCell label="יום" en="Day"><Num value={s?.returns?.day} asPct signed /></StatCell>
          <StatCell label="שבוע" en="WTD"><Num value={s?.returns?.wtd} asPct signed /></StatCell>
          <StatCell label="חודש" en="MTD"><Num value={s?.returns?.mtd} asPct signed /></StatCell>
          <StatCell label="שנה נוכ׳" en="YTD"><Num value={s?.returns?.ytd} asPct signed /></StatCell>
          <StatCell label="שנה" en="1Y"><Num value={s?.returns?.one_year} asPct signed /></StatCell>
          <StatCell label="מצטבר" en="Total"><Num value={s?.returns?.total_twr} asPct signed /></StatCell>
          <StatCell
            label="שנתי"
            en="Annual."
            hint="תשואה מצטברת מוקרנת לקצב שנתי. מוצגת רק כשיש לפחות 90 יום."
          >
            {gated(s?.returns?.annualized, true)}
          </StatCell>
        </StatRail>
      </Panel>

      {/* ── Hero equity curve + risk side-rail ──────────────────────── */}
      <div className="grid gap-3 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="עקומת התיק"
          subtitle="Equity Curve"
          actions={<Tabs items={CHART_MODES} value={mode} onChange={setMode} size="sm" ariaLabel="מצב גרף" />}
        >
          {curve.data?.available ? (
            <EquityChart points={curve.data.points} mode={mode} />
          ) : (
            <p className="py-16 text-center text-[12.5px] text-muted">
              הגרף יופיע לאחר סנכרון היסטוריה (מסך סנכרון).
            </p>
          )}
          <p className="t-help mt-2">▲ הפקדה · ▼ משיכה — כדי שתזרים לא ייראה כרווח/הפסד.</p>
        </Panel>

        <div className="flex flex-col gap-3">
          <Panel title="Drawdown" padding="none">
            <StatRail cols="grid-cols-3">
              <StatCell label="מקסימלי" en="Max">
                <Num value={s?.risk?.max_drawdown} asPct signed />
                {s?.risk?.max_drawdown_date && (
                  <div className="num text-[9.5px] font-normal text-faint">{s.risk.max_drawdown_date}</div>
                )}
              </StatCell>
              <StatCell label="נוכחי" en="Current">
                <Num value={s?.risk?.current_drawdown} asPct signed />
              </StatCell>
              <StatCell label="ימי החלמה" en="Recovery">
                <span className="num">{s?.risk?.recovery_days ?? "—"}</span>
              </StatCell>
            </StatRail>
          </Panel>
          <Panel title="מדדי סיכון" subtitle="Risk" padding="none">
            <StatRail cols="grid-cols-3">
              <StatCell label="תנודתיות" en="Vol" hint="סטיית תקן של תשואות יומיות × √252. דורש 60 ימי מסחר.">
                {gated(s?.risk?.volatility, true)}
              </StatCell>
              <StatCell label="Sharpe" hint="תשואה עודפת מעל ריבית חסרת סיכון ביחס לתנודתיות. דורש 60 ימי מסחר.">
                {gated(s?.risk?.sharpe, false)}
              </StatCell>
              <StatCell label="Sortino" hint="כמו Sharpe אך מעניש רק תנודתיות שלילית. דורש 60 ימי מסחר.">
                {gated(s?.risk?.sortino, false)}
              </StatCell>
            </StatRail>
          </Panel>
          <Panel title="תשואת כסף" subtitle="Money-Weighted" padding="none">
            <StatRail cols="grid-cols-1">
              <StatCell label="XIRR שנתי" en="Annualized">
                {s?.returns?.xirr != null ? (
                  <Num value={s.returns.xirr} asPct signed />
                ) : (
                  <span className="text-[12px] font-normal text-faint">אין מספיק תזרימים</span>
                )}
              </StatCell>
            </StatRail>
          </Panel>
        </div>
      </div>

      {/* ── Monthly returns + cash flows ────────────────────────────── */}
      <div className="grid gap-3 lg:grid-cols-3">
        <Panel className="lg:col-span-2" title="תשואה חודשית" subtitle="Monthly">
          {monthly.data?.available && Object.keys(monthly.data.months).length > 0 ? (
            <MonthlyChart months={monthly.data.months} />
          ) : (
            <p className="py-10 text-center text-[12.5px] text-muted">אין עדיין נתונים חודשיים.</p>
          )}
        </Panel>
        <Panel title="תזרימים ועלויות" subtitle="Cash & Costs" padding="none">
          <StatRail cols="grid-cols-2">
            <StatCell label="הפקדות" en="Deposits"><Num value={s?.cash?.deposits} currency="USD" /></StatCell>
            <StatCell label="משיכות" en="Withdrawals"><Num value={s?.cash?.withdrawals} currency="USD" /></StatCell>
            <StatCell label="דיבידנדים" en="Dividends"><Num value={s?.cash?.dividends} currency="USD" /></StatCell>
            <StatCell label="מס במקור" en="Wht. tax"><Num value={s?.cash?.withholding_tax} currency="USD" /></StatCell>
            <StatCell label="עמלות" en="Fees"><Num value={s?.cash?.fees} currency="USD" /></StatCell>
            <StatCell label="ריבית נטו" en="Interest"><Num value={s?.cash?.interest_net} currency="USD" /></StatCell>
          </StatRail>
        </Panel>
      </div>

      <p className="t-help leading-relaxed">
        TWR מודד ביצועי השקעות בנטרול עיתוי ההפקדות — ההשוואה הנכונה מול מדדים. XIRR משקלל גם את עיתוי
        הכסף שלך. מקור: NAV יומי מ־Flex.
      </p>
    </div>
  );
}

function EquityChart({ points, mode }: { points: CurvePoint[]; mode: ChartMode }) {
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
      grid: { left: 56, right: 16, top: 18, bottom: 40 },
      tooltip: {
        trigger: "axis",
        backgroundColor: t.panel,
        borderColor: t.line,
        textStyle: { color: t.fg, fontSize: 11 },
        valueFormatter: (v) =>
          mode === "nav" ? Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 }) : `${Number(v).toFixed(2)}%`,
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: t.line } },
        axisLabel: { color: t.faint, fontSize: 10 },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { color: t.line, opacity: 0.6 } },
        axisLabel: {
          color: t.faint,
          fontSize: 10,
          formatter: (v: number) =>
            mode === "nav" ? v.toLocaleString("en-US") : `${v}%`,
        },
      },
      dataZoom: [
        { type: "inside" },
        { type: "slider", height: 16, bottom: 8, borderColor: t.line, textStyle: { color: t.faint, fontSize: 9 } },
      ],
      series: [
        {
          type: "line",
          data: series,
          showSymbol: false,
          lineStyle: { width: 2, color },
          areaStyle: { color, opacity: 0.08 },
          markPoint: {
            symbol: "circle",
            symbolSize: 1,
            label: { show: true, fontSize: 12, color: t.fg },
            data: flowMarkers,
          },
        },
      ],
    } as EChartsOption;
  }, [points, mode]);

  return <EChart option={option} height={340} />;
}

function MonthlyChart({ months }: { months: Record<string, number> }) {
  const option = useMemo<EChartsOption>(() => {
    const t = chartTokens();
    const keys = Object.keys(months);
    return {
      backgroundColor: "transparent",
      grid: { left: 56, right: 16, top: 18, bottom: 28 },
      tooltip: {
        trigger: "axis",
        backgroundColor: t.panel,
        borderColor: t.line,
        textStyle: { color: t.fg, fontSize: 11 },
        valueFormatter: (v) => `${Number(v).toFixed(2)}%`,
      },
      xAxis: {
        type: "category",
        data: keys,
        axisLine: { lineStyle: { color: t.line } },
        axisLabel: { color: t.faint, fontSize: 10 },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: t.line, opacity: 0.6 } },
        axisLabel: { color: t.faint, fontSize: 10, formatter: (v: number) => `${v}%` },
      },
      series: [
        {
          type: "bar",
          data: keys.map((k) => {
            const v = +(months[k] * 100).toFixed(3);
            return { value: v, itemStyle: { color: v >= 0 ? t.gain : t.loss, borderRadius: 2 } };
          }),
          barMaxWidth: 28,
          label: {
            show: keys.length <= 14,
            position: "top",
            fontSize: 9.5,
            color: t.faint,
            formatter: (p: { value?: unknown }) => `${Number(p.value).toFixed(1)}%`,
          },
        },
      ],
    } as EChartsOption;
  }, [months]);

  return <EChart option={option} height={240} />;
}
