import { Num } from "@/components/ui/num";

/*
  Stat tile: small muted label, large tabular value, optional signed delta.
  Identity is carried by the label; sign carries polarity (never color alone).
*/
export function Stat({
  label,
  value,
  currency,
  signed,
  asPct,
  sub,
  title,
}: {
  label: string;
  value: string | number | null | undefined;
  currency?: string;
  signed?: boolean;
  asPct?: boolean;
  sub?: React.ReactNode;
  title?: string;
}) {
  return (
    <div className="min-w-0" title={title}>
      <div className="truncate text-[11px] text-faint">{label}</div>
      <div className="mt-0.5 text-[17px] font-semibold leading-tight">
        <Num value={value} currency={currency} signed={signed} asPct={asPct} />
      </div>
      {sub ? <div className="mt-0.5 text-[10.5px] text-faint">{sub}</div> : null}
    </div>
  );
}
