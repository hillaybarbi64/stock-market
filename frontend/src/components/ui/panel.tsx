/*
  Panel — the widget surface primitive (Legend language). Every panel is a
  glossy elevated "widget" with a header that carries a drag-handle affordance,
  a leading green tick, the title, an optional English sub-label, and a tools
  slot on the trailing edge. Backward compatible: title/subtitle/info/actions/
  children/className/bodyClassName/padding/elevation/revealIndex all still work.
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
  grip = true,
}: {
  title?: string;
  /** English sub-label shown quietly next to the title (e.g. "Net Liquidation") */
  subtitle?: string;
  info?: React.ReactNode;
  /** trailing-edge tools: tabs, badges, range chips */
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  padding?: "none" | "sm" | "md";
  /** kept for API compat; the widget already carries elevation */
  elevation?: "flat" | "raised";
  /** opt-in staggered entrance; pass a 0-based order index */
  revealIndex?: number;
  /** show the drag-handle affordance in the header */
  grip?: boolean;
}) {
  const reveal =
    revealIndex !== undefined
      ? { className: "panel-reveal", style: { "--reveal-i": revealIndex } as React.CSSProperties }
      : null;
  const pad = padding === "none" ? "" : padding === "sm" ? "p-3" : "p-3.5";
  void elevation;
  const hasHeader = title || actions || subtitle;
  return (
    <section
      className={`widget ${reveal?.className ?? ""} ${className}`}
      style={reveal?.style}
    >
      {hasHeader && (
        <header className="widget-head flex items-center gap-2.5 border-b border-line px-3.5 py-2.5">
          {grip && title && <span aria-hidden className="grip" />}
          {title && <span aria-hidden className="wtick" />}
          <div className="flex min-w-0 items-baseline gap-2">
            {title && <h2 className="t-h2 truncate text-fg">{title}</h2>}
            {subtitle && (
              <span className="truncate text-[10px] tracking-wide text-faint" dir="ltr">
                {subtitle}
              </span>
            )}
            {info}
          </div>
          {actions && <div className="ms-auto flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={bodyClassName ?? pad}>{children}</div>
    </section>
  );
}
