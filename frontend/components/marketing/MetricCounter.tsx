"use client";

import { useEffect, useMemo, useState } from "react";

type MetricCounterProps = {
  end: number;
  prefix?: string;
  suffix?: string;
  durationMs?: number;
};

export function MetricCounter({
  end,
  prefix = "",
  suffix = "",
  durationMs = 1400,
}: MetricCounterProps) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    let frame = 0;
    const start = performance.now();

    function tick(now: number) {
      const progress = Math.min((now - start) / durationMs, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(end * eased));

      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      }
    }

    frame = requestAnimationFrame(tick);

    return () => cancelAnimationFrame(frame);
  }, [durationMs, end]);

  const formatted = useMemo(() => new Intl.NumberFormat("en-IN").format(value), [value]);

  return (
    <span>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}
