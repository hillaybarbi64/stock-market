export function Panel({
  title,
  actions,
  children,
  className = "",
}: {
  title?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-md border border-line bg-panel ${className}`}>
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
