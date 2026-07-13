/*
  Financial value display primitives.

  <Num> renders a number LTR with tabular digits inside RTL text.
  Sign coloring is opt-in (signed) — we do not paint everything green/red.
*/

const nf = (opts: Intl.NumberFormatOptions) => new Intl.NumberFormat("en-US", opts);

const FORMATTERS = {
  money: nf({ minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  price: nf({ minimumFractionDigits: 2, maximumFractionDigits: 4 }),
  qty: nf({ maximumFractionDigits: 6 }),
  pct: nf({ minimumFractionDigits: 2, maximumFractionDigits: 2 }),
} as const;

export interface NumProps {
  value: number | string | null | undefined;
  kind?: keyof typeof FORMATTERS;
  currency?: string;
  /** percent value expressed as fraction (0.0123 → ‎1.23%) */
  asPct?: boolean;
  /** color by sign and render explicit + for gains */
  signed?: boolean;
  className?: string;
}

export function Num({ value, kind = "money", currency, asPct, signed, className = "" }: NumProps) {
  if (value === null || value === undefined || value === "") {
    return <span className={`num text-faint ${className}`}>—</span>;
  }
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return <span className={`num text-faint ${className}`}>—</span>;

  const display = asPct ? n * 100 : n;
  const formatted = FORMATTERS[asPct ? "pct" : kind].format(Math.abs(display));
  const sign = display < 0 ? "-" : signed && display > 0 ? "+" : "";
  const tone = signed ? (display > 0 ? "text-gain" : display < 0 ? "text-loss" : "text-muted") : "";

  return (
    <span className={`num ${tone} ${className}`}>
      {sign}
      {formatted}
      {asPct ? "%" : ""}
      {currency ? <span className="ms-1 text-[0.85em] text-faint">{currency}</span> : null}
    </span>
  );
}

/** Ticker symbol — always LTR, medium weight. */
export function Sym({ children, className = "" }: { children: string; className?: string }) {
  return <span className={`sym ${className}`}>{children}</span>;
}
