"use client";

import { useEffect, useState } from "react";

/*
  A quiet live clock for the top bar. Renders nothing until mounted to avoid
  hydration mismatch, then ticks once a second (local time, 24h).
*/
export function Clock() {
  const [now, setNow] = useState<string | null>(null);
  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString("en-GB"));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="num tabular-nums">{now ?? "--:--:--"}</span>;
}
