export function Panel({
  title,
  actions,
  children,
  className = "",
  revealIndex,
}: {
  title?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  /** opt-in staggered entrance; pass a 0-based order index */
  revealIndex?: number;
}) {
  const reveal =
    revealIndex !== undefined
      ? { className: "panel-reveal", style: { "--reveal-i": revealIndex } as React.CSSProperties }
      : null;
  return (
    <section
      className={`rounded-md border border-line bg-panel ${reveal?.className ?? ""} ${className}`}
      style={reveal?.style}
    >
      {(title || actions) && (
        <header className="flex h-9 items-center justify-between border-b border-line px-3.5">
          <h2 className="text-[12.5px] font-medium text-muted">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-3.5">{children}</div>
    </section>
  );
}
