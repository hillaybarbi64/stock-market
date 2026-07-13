/*
  Panel — the surface primitive. Backward compatible (title/actions/children/
  className/revealIndex still work) plus new options for the redesign:
  subtitle, an info slot in the header, padding density, and elevation.
*/
export function Panel({
  title,
  subtitle,
  info,
  actions,
  children,
  className = "",
  bodyClassName,
  padding = "md",
  elevation = "flat",
  revealIndex,
}: {
  title?: string;
  subtitle?: string;
  info?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  padding?: "none" | "sm" | "md";
  elevation?: "flat" | "raised";
  /** opt-in staggered entrance; pass a 0-based order index */
  revealIndex?: number;
}) {
  const reveal =
    revealIndex !== undefined
      ? { className: "panel-reveal", style: { "--reveal-i": revealIndex } as React.CSSProperties }
      : null;
  const pad = padding === "none" ? "" : padding === "sm" ? "p-3" : "p-3.5";
  const elev = elevation === "raised" ? "elev-1" : "";
  return (
    <section
      className={`rounded-md border border-line bg-panel ${elev} ${reveal?.className ?? ""} ${className}`}
      style={reveal?.style}
    >
      {(title || actions || subtitle) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-3.5 py-2">
          <div className="flex min-w-0 items-center gap-1.5">
            {title && <h2 className="t-h2 truncate text-fg">{title}</h2>}
            {info}
            {subtitle && <span className="t-help truncate">· {subtitle}</span>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName ?? pad}>{children}</div>
    </section>
  );
}
