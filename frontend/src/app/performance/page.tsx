"use client";

import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import { chartTokens, EChart } from "@/components/charts/echart";
import { Panel } from "@/components/ui/panel";
import { Num } from "@/components/ui/num";
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
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">ביצועים</h1>
        {s?.as_of && (
          <span className="num text-[11px] text-faint">
            {s.since} → {s.as_of} · {s.days_available} ימים
          </span>
        )}
      </div>

      <Panel title="תשואות (TWR — בנטרול הפקדות ומשיכות)">
        <div className="grid grid-cols-3 gap-x-6 gap-y-4 sm:grid-cols-4 lg:grid-cols-7">
          <Ret label="יום" value={s?.returns?.day} />
          <Ret label="מתחילת השבוע" value={s?.returns?.wtd} />
          <Ret label="מתחילת החודש" value={s?.returns?.mtd} />
          <Ret label="מתחילת השנה" value={s?.returns?.ytd} />
          <Ret label="שנה אחרונה" value={s?.returns?.one_year} />
          <Ret label="מצטבר" value={s?.returns?.total_twr} />
          <GatedStat
            label="שנתי (Annualized)"
            gated={s?.returns?.annualized}
            asPct
            tooltip="תשואה מצטברת מוקרנת לקצב שנתי. מוצגת רק כשיש לפחות 90 יום."
          />
        </div>
        <p className="mt-3 text-[10.5px] leading-relaxed text-faint">
          TWR מודד את ביצועי ההשקעות בנטרול מלא של עיתוי ההפקדות — זו ההשוואה הנכונה מול
          מדדים. XIRR (למטה) משקלל גם את עיתוי הכסף שלך. מקור: NAV יומי מ־Flex.
        </p>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="תשואת כסף (Money-Weighted)">
          <div className="grid grid-cols-2 gap-x-6 gap-y-4">
            <div>
              <div className="text-[11px] text-faint">XIRR שנתי</div>
              <div className="mt-0.5 text-[17px] font-semibold">
                {s?.returns?.xirr != null ? (
                  <Num value={s.returns.xirr} asPct signed />
                ) : (
                  <span className="text-[12px] font-normal text-faint">
                    לא ניתן לחישוב (אין מספיק תזרימים)
                  </span>
                )}
              </div>
            </div>
          </div>
        </Panel>
        <Panel title="Drawdown">
          <div className="grid grid-cols-3 gap-x-6 gap-y-4">
            <div>
              <div className="text-[11px] text-faint">מקסימלי</div>
              <div className="mt-0.5 text-[17px] font-semibold">
                <Num value={s?.risk?.max_drawdown} asPct signed />
              </div>
              {s?.risk?.max_drawdown_date && (
                <div className="num mt-0.5 text-[10px] text-faint">{s.risk.max_drawdown_date}</div>
              )}
            </div>
            <div>
              <div className="text-[11px] text-faint">נוכחי</div>
              <div className="mt-0.5 text-[17px] font-semibold">
                <Num value={s?.risk?.current_drawdown} asPct signed />
              </div>
            </div>
            <div>
              <div className="text-[11px] text-faint">ימי התאוששות</div>
              <div className="num mt-0.5 text-[17px] font-semibold">
                {s?.risk?.recovery_days ?? "—"}
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <Panel
        title="עקומת התיק"
        actions={
          <div className="flex gap-1" dir="ltr">
            {(
              [
                ["nav", "שווי"],
                ["return", "תשואה %"],
                ["drawdown", "Drawdown"],
              ] as [ChartMode, string][]
            ).map(([m, label]) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`rounded-sm px-2 py-0.5 text-[11px] transition-colors ${
                  mode === m ? "bg-subtle font-medium text-fg" : "text-muted hover:bg-hover"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        }
      >
        {curve.data?.available ? (
          <EquityChart points={curve.data.points} mode={mode} />
        ) : (
          <p className="py-10 text-center text-[12.5px] text-muted">
            הגרף יופיע לאחר סנכרון היסטוריה (מסך סנכרון).
          </p>
        )}
        <p className="mt-2 text-[10.5px] text-faint">
          ▲ מסמן הפקדה, ▼ מסמן משיכה — כדי שתזרים לא ייראה כרווח או הפסד.
        </p>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="מדדי סיכון">
          <div className="grid grid-cols-3 gap-x-6 gap-y-4">
            <GatedStat
              label="תנודתיות שנתית"
              gated={s?.risk?.volatility}
              asPct
              tooltip="סטיית תקן של תשואות יומיות × √252. דורש 60 ימי מסחר."
            />
            <GatedStat
              label="Sharpe"
              gated={s?.risk?.sharpe}
              tooltip="תשואה עודפת מעל ריבית חסרת סיכון ביחס לתנודתיות. דורש 60 ימי מסחר."
            />
            <GatedStat
              label="Sortino"
              gated={s?.risk?.sortino}
              tooltip="כמו Sharpe אך מעניש רק תנודתיות שלילית. דורש 60 ימי מסחר."
            />
          </div>
        </Panel>
        <Panel title="תזרימים ועלויות (מצטבר, במטבע הבסיס)">
          <div className="grid grid-cols-3 gap-x-6 gap-y-4">
            <MiniStat label="הפקדות" value={s?.cash?.deposits} />
            <MiniStat label="משיכות" value={s?.cash?.withdrawals} />
            <MiniStat label="דיבידנדים" value={s?.cash?.dividends} />
            <MiniStat label="מס במקור" value={s?.cash?.withholding_tax} />
            <MiniStat label="עמלות ודמי ניהול" value={s?.cash?.fees} />
            <MiniStat label="ריבית (נטו)" value={s?.cash?.interest_net} />
          </div>
        </Panel>
      </div>

      <Panel title="תשואה חודשית">
        {monthly.data?.available && Object.keys(monthly.data.months).length > 0 ? (
          <MonthlyChart months={monthly.data.months} />
        ) : (
          <p className="py-6 text-center text-[12.5px] text-muted">אין עדיין נתונים חודשיים.</p>
        )}
      </Panel>
    </div>
  );
}

function Ret({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div>
      <div className="text-[11px] text-faint">{label}</div>
      <div className="mt-0.5 text-[15px] font-semibold">
        <Num value={value} asPct signed />
      </div>
    </div>
  );
}

function GatedStat({
  label,
  gated,
  asPct,
  tooltip,
}: {
  label: string;
  gated: Gated | undefined;
  asPct?: boolean;
  tooltip?: string;
}) {
  return (
    <div title={tooltip}>
      <div className="text-[11px] text-faint">{label}</div>
      {gated?.sufficient ? (
        <div className="mt-0.5 text-[15px] font-semibold">
          {asPct ? (
            <Num value={gated.value} asPct />
          ) : (
            <span className="num">{gated.value?.toFixed(2)}</span>
          )}
        </div>
      ) : (
        <div className="mt-1 text-[11px] leading-snug text-faint">
          אין מספיק נתונים
          <br />
          <span className="num">
            {gated ? `${gated.available}/${gated.required}` : "—"}
          </span>{" "}
          ימים
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: number | null | undefined }) {
  return (
    <div>
      <div className="text-[11px] text-faint">{label}</div>
      <div className="mt-0.5 text-[13.5px] font-medium">
        <Num value={value} currency="USD" />
      </div>
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
