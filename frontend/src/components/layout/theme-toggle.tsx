"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

const emptySubscribe = () => () => {};

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  // Hydration-safe "is client" check without setState-in-effect.
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);
  if (!mounted) return <div className="w-14" />;

  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="rounded-sm border border-line px-2.5 py-1 text-[11.5px] text-muted transition-colors hover:bg-hover hover:text-fg"
    >
      {dark ? "מצב בהיר" : "מצב כהה"}
    </button>
  );
}
