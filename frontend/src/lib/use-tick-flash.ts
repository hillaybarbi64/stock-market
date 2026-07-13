"use client";

import { useEffect, useRef } from "react";

/*
  The single reusable liveness primitive.

  On each real value change it retriggers a directional background wash on the
  target span. The classList.remove → forced reflow → classList.add dance is
  what makes a second same-direction tick re-fire the keyframe (a plain state
  swap of "up" → "up" would not restart the animation). Background-only, so it
  never fights signed P&L coloring and causes zero layout shift.

  Called unconditionally (enabled gates the effect, not the hook) to keep the
  rules of hooks satisfied in <Num>, which has null/NaN early returns.
*/
export function useTickFlash(n: number | null, enabled: boolean) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef<number | null>(null);

  useEffect(() => {
    const el = ref.current;
    const before = prev.current;
    prev.current = n;
    if (!enabled || el == null || n == null || before == null || n === before) return;

    el.dataset.dir = n > before ? "up" : "down";
    el.classList.remove("is-flashing");
    void el.offsetWidth; // force reflow so the keyframe restarts
    el.classList.add("is-flashing");
  }, [n, enabled]);

  return ref;
}
