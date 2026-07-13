"use client";

/*
  Tabs — a lightweight controlled segmented control used across the redesign
  for progressive disclosure (chart modes, table views, time ranges). RTL-safe,
  keyboard-navigable, uses the design tokens.
*/

export interface TabItem<T extends string = string> {
  value: T;
  label: string;
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  size = "md",
  ariaLabel,
}: {
  items: readonly TabItem<T>[];
  value: T;
  onChange: (v: T) => void;
  size?: "sm" | "md";
  ariaLabel?: string;
}) {
  const pad = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-[12px]";
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-0.5 rounded-md bg-subtle p-0.5"
      dir="ltr"
    >
      {items.map((it) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(it.value)}
            className={`press rounded-sm ${pad} transition-colors ${
              active ? "bg-panel font-medium text-fg elev-1" : "text-muted hover:text-fg"
            }`}
          >
            {it.label}
          </button>
        );
      })}
    </div>
  );
}
