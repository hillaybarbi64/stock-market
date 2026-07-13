/*
  Data provenance marker: every panel that shows account data says where the
  data came from and how fresh it is. Stale data is clearly labeled — never
  silently presented as live.
*/
export function SourceBadge({
  source,
  stale,
  asOf,
}: {
  source: string | null | undefined;
  stale: boolean | undefined;
  asOf?: string | null;
}) {
  if (!source) return null;
  const label = source === "ibkr_gateway" ? "IBKR · LIVE" : "SNAPSHOT";
  return (
    <span className="flex items-center gap-2" dir="ltr">
      <span
        className={`sym rounded-sm px-1.5 py-px text-[9.5px] font-medium ${
          stale ? "bg-subtle text-warn" : "bg-subtle text-muted"
        }`}
      >
        {stale ? `${label} · STALE` : label}
      </span>
      {asOf && (
        <span className="num text-[10px] text-faint">
          {new Date(asOf).toLocaleTimeString("en-GB")}
        </span>
      )}
    </span>
  );
}
