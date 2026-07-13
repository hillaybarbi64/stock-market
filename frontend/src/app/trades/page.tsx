"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import { Num, Sym } from "@/components/ui/num";
import { apiGet } from "@/lib/api";

interface TradeRow {
  exec_id: string;
  order_id: string | null;
  symbol: string;
  name: string | null;
  side: "BUY" | "SELL";
  quantity: string;
  price: string;
  trade_time: string;
  exchange: string | null;
  order_type: string | null;
  commission: string | null;
  realized_pnl_ib: string | null;
  currency: string;
  net_amount: string | null;
  source: string;
}

interface TradesResponse {
  total: number;
  limit: number;
  offset: number;
  trades: TradeRow[];
}

const PAGE_SIZE = 50;

export default function TradesPage() {
  const [symbol, setSymbol] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);

  const params = new URLSearchParams();
  if (symbol) params.set("symbol", symbol);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  params.set("limit", String(PAGE_SIZE));
  params.set("offset", String(page * PAGE_SIZE));

  const { data, isLoading } = useQuery({
    queryKey: ["trades", symbol, dateFrom, dateTo, page],
    queryFn: () => apiGet<TradesResponse>(`/trades?${params.toString()}`),
  });

  const exportCsv = () => {
    if (!data?.trades.length) return;
    const header = "exec_id,symbol,side,quantity,price,trade_time,exchange,order_type,commission,realized_pnl,currency,net_amount";
    const lines = data.trades.map((t) =>
      [t.exec_id, t.symbol, t.side, t.quantity, t.price, t.trade_time, t.exchange ?? "", t.order_type ?? "", t.commission ?? "", t.realized_pnl_ib ?? "", t.currency, t.net_amount ?? ""].join(","),
    );
    const blob = new Blob([header + "\n" + lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `trades_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[17px] font-semibold tracking-tight">עסקאות</h1>
        {data && <span className="num text-[11px] text-faint">{data.total} ביצועים</span>}
      </div>

      <Panel>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="סימול">
            <input
              value={symbol}
              onChange={(e) => {
                setSymbol(e.target.value.toUpperCase());
                setPage(0);
              }}
              placeholder="AAPL"
              className="sym w-28 rounded-sm border border-line bg-bg px-2 py-1 text-[12px] outline-none focus:border-line-strong"
            />
          </Field>
          <Field label="מתאריך">
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPage(0);
              }}
              className="num rounded-sm border border-line bg-bg px-2 py-1 text-[12px] outline-none focus:border-line-strong"
            />
          </Field>
          <Field label="עד תאריך">
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPage(0);
              }}
              className="num rounded-sm border border-line bg-bg px-2 py-1 text-[12px] outline-none focus:border-line-strong"
            />
          </Field>
          <button
            type="button"
            onClick={exportCsv}
            disabled={!data?.trades.length}
            className="ms-auto rounded-sm border border-line px-3 py-1 text-[12px] text-muted transition-colors hover:bg-hover hover:text-fg disabled:opacity-40"
          >
            ייצוא CSV
          </button>
        </div>
      </Panel>

      <Panel>
        {isLoading ? (
          <div className="h-40 animate-pulse rounded-sm bg-subtle" />
        ) : !data?.trades.length ? (
          <div className="py-10 text-center">
            <p className="text-[13.5px] font-medium">אין עסקאות להצגה</p>
            <p className="mt-1 text-[12.5px] text-muted">
              עסקאות יופיעו לאחר סנכרון Flex או קליטה חיה מה־Gateway.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="text-[10.5px] text-faint">
                  <th className="pb-1.5 text-start font-normal">זמן</th>
                  <th className="pb-1.5 text-start font-normal">נכס</th>
                  <th className="pb-1.5 text-start font-normal">צד</th>
                  <th className="pb-1.5 text-end font-normal">כמות</th>
                  <th className="pb-1.5 text-end font-normal">מחיר</th>
                  <th className="pb-1.5 text-end font-normal">שווי</th>
                  <th className="pb-1.5 text-end font-normal">עמלה</th>
                  <th className="pb-1.5 text-end font-normal">P&L ממומש</th>
                  <th className="pb-1.5 text-start font-normal">סוג</th>
                  <th className="pb-1.5 text-start font-normal">בורסה</th>
                  <th className="pb-1.5 text-start font-normal">מקור</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t) => (
                  <tr key={t.exec_id} className="border-t border-line hover:bg-hover">
                    <td className="num py-1.5 text-[11.5px]">
                      {new Date(t.trade_time).toLocaleString("he-IL", {
                        dateStyle: "short",
                        timeStyle: "short",
                      })}
                    </td>
                    <td className="py-1.5"><Sym>{t.symbol}</Sym></td>
                    <td className="py-1.5">
                      <span className={`sym text-[10.5px] font-medium ${t.side === "BUY" ? "text-gain" : "text-loss"}`}>
                        {t.side}
                      </span>
                    </td>
                    <td className="py-1.5 text-end"><Num value={t.quantity} kind="qty" /></td>
                    <td className="py-1.5 text-end"><Num value={t.price} kind="price" /></td>
                    <td className="py-1.5 text-end"><Num value={t.net_amount} currency={t.currency} /></td>
                    <td className="py-1.5 text-end"><Num value={t.commission} /></td>
                    <td className="py-1.5 text-end"><Num value={t.realized_pnl_ib} signed /></td>
                    <td className="py-1.5"><span className="sym text-[10.5px] text-faint">{t.order_type ?? "—"}</span></td>
                    <td className="py-1.5"><span className="sym text-[10.5px] text-faint">{t.exchange ?? "—"}</span></td>
                    <td className="py-1.5"><span className="sym text-[9.5px] text-faint">{t.source.toUpperCase()}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total > PAGE_SIZE && (
          <div className="mt-3 flex items-center justify-between text-[11.5px] text-muted" dir="ltr">
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="rounded-sm border border-line px-2 py-0.5 hover:bg-hover disabled:opacity-40"
            >
              ← Newer
            </button>
            <span className="num">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, data.total)} / {data.total}
            </span>
            <button
              type="button"
              disabled={(page + 1) * PAGE_SIZE >= data.total}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-sm border border-line px-2 py-0.5 hover:bg-hover disabled:opacity-40"
            >
              Older →
            </button>
          </div>
        )}
      </Panel>
      <p className="text-[10.5px] text-faint">
        P&L ממומש לפי דיווח IBKR (שיטת FIFO, אחרי עמלות). מקור FLEX = מהדוח ההיסטורי; GATEWAY = נקלט חי.
      </p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-[10.5px] text-faint">
      {label}
      {children}
    </label>
  );
}
