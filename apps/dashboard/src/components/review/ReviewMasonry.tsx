"use client";

import {Children, useEffect, useMemo, useState, type ReactNode} from "react";

function useResponsiveColumnCount() {
  const [count, setCount] = useState(1);

  useEffect(() => {
    function update() {
      const width = window.innerWidth;
      if (width >= 1280) setCount(3);
      else if (width >= 640) setCount(2);
      else setCount(1);
    }
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return count;
}

export function ReviewMasonry({
  children,
  columnCount,
  variant = "fluid",
}: {
  children: ReactNode;
  /** When set, caps columns (batch page). Otherwise 1 / 2 / 3 by viewport. */
  columnCount?: number;
  variant?: "fluid" | "fixed";
}) {
  const responsiveCount = useResponsiveColumnCount();
  const items = useMemo(() => Children.toArray(children).filter(Boolean), [children]);
  const maxColumns = columnCount ?? responsiveCount;
  const bucketCount = useMemo(() => {
    if (items.length <= 1) return 1;
    if (variant === "fixed") return Math.max(1, Math.min(maxColumns, items.length));
    // Inbox (Published / Scheduled / …): keep column width stable even with few cards.
    return Math.max(1, maxColumns);
  }, [items.length, maxColumns, variant]);

  const columns = useMemo(() => {
    const buckets: ReactNode[][] = Array.from({length: bucketCount}, () => []);
    items.forEach((child, index) => {
      buckets[index % bucketCount].push(child);
    });
    return buckets;
  }, [bucketCount, items]);

  const gapClass = variant === "fixed" ? "gap-5" : "gap-4 sm:gap-5";
  const outerClass =
    variant === "fixed"
      ? `mx-auto flex w-full max-w-full items-start justify-center ${gapClass}`
      : `mx-auto flex w-full max-w-[1180px] items-start justify-center ${gapClass}`;

  const columnClass =
    variant === "fixed"
      ? `flex min-w-0 w-full max-w-[22rem] flex-col ${gapClass}`
      : `flex min-w-0 flex-1 basis-0 flex-col ${gapClass}`;

  return (
    <div className={outerClass}>
      {columns.map((bucket, index) => (
        <div key={index} className={columnClass}>
          {bucket}
        </div>
      ))}
    </div>
  );
}
