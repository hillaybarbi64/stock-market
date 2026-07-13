/*
  StatRail / StatCell — the dense "terminal" metric strip from the Legend
  dashboard, promoted to a shared primitive. A StatRail is a hairline grid of
  StatCells (cells on a bg-line grid so 1px seams separate them); each cell is
  a quiet label (+ optional English sub-label) over a prominent tabular value.
  Drop a StatRail into a padding="none" Panel to get an edge-to-edge KPI band.
*/

export function StatRail({
  children,
  cols = "grid-cols-2 sm:grid-cols-4",
  className = "",
}: {
  children: React.ReactNode;
  /** Tailwind grid-template-columns utilities controlling the cell count */
  cols?: string;
  className?: string;
}) {
  return <div className={`grid gap-px bg-line ${cols} ${className}`}>{children}</div>;
}

export function StatCell({
  label,
  en,
  hint,
  children,
}: {
  label: string;
  /** quiet English sub-label shown next to the Hebrew label */
  en?: string;
  /** native title tooltip (explain-me) */
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-panel px-3.5 py-2.5" title={hint}>
      <div className="flex items-baseline gap-1.5">
        <span className="truncate text-[11px] text-muted">{label}</span>
        {en && (
          <span className="shrink-0 text-[9px] text-faint" dir="ltr">
            {en}
          </span>
        )}
      </div>
      <div className="num mt-0.5 text-[15px] font-semibold">{children}</div>
    </div>
  );
}
