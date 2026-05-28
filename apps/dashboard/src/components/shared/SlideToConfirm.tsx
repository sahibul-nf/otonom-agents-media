"use client";

import {ChevronRight, Loader2} from "lucide-react";
import {useEffect, useRef, useState} from "react";

interface SlideToConfirmProps {
  label: string;
  activeLabel?: string;
  onConfirm: () => void;
  disabled?: boolean;
  isLoading?: boolean;
  className?: string;
}

export function SlideToConfirm({
  label,
  activeLabel = "Release to confirm...",
  onConfirm,
  disabled = false,
  isLoading = false,
  className = "",
}: SlideToConfirmProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragX, setDragX] = useState(0);
  const [hasConfirmed, setHasConfirmed] = useState(false);

  // Maximum drag distance calculation
  const getMaxTravel = () => {
    if (!containerRef.current || !handleRef.current) return 0;
    return containerRef.current.clientWidth - handleRef.current.clientWidth - 8; // 8px for margins/padding
  };

  useEffect(() => {
    if (isLoading) {
      setHasConfirmed(true);
    } else if (!isLoading && hasConfirmed) {
      // Reset if loading finishes
      setHasConfirmed(false);
      setDragX(0);
    }
  }, [isLoading]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || hasConfirmed || disabled) return;
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const maxTravel = getMaxTravel();
      const currentX = e.clientX - rect.left - 24; // offset to center handle

      const clampedX = Math.max(0, Math.min(maxTravel, currentX));
      setDragX(clampedX);

      // Trigger if reached near the very end
      if (clampedX >= maxTravel * 0.98) {
        setIsDragging(false);
        setHasConfirmed(true);
        setDragX(maxTravel);
        onConfirm();
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isDragging || hasConfirmed || disabled) return;
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const maxTravel = getMaxTravel();
      const touch = e.touches[0];
      if (!touch) return;
      const currentX = touch.clientX - rect.left - 24;

      const clampedX = Math.max(0, Math.min(maxTravel, currentX));
      setDragX(clampedX);

      if (clampedX >= maxTravel * 0.98) {
        setIsDragging(false);
        setHasConfirmed(true);
        setDragX(maxTravel);
        onConfirm();
      }
    };

    const handleMouseUp = () => {
      if (!isDragging) return;
      setIsDragging(false);

      const maxTravel = getMaxTravel();
      if (dragX < maxTravel * 0.98) {
        // Reset position with smooth css transition
        setDragX(0);
      }
    };

    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
      window.addEventListener("touchmove", handleTouchMove, {passive: true});
      window.addEventListener("touchend", handleMouseUp);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("touchend", handleMouseUp);
    };
  }, [isDragging, dragX, hasConfirmed, disabled, onConfirm]);

  const handleStart = () => {
    if (disabled || hasConfirmed) return;
    setIsDragging(true);
  };

  const travel = getMaxTravel();
  const progressPercent = travel > 0 ? (dragX / travel) * 100 : 0;

  return (
    <div
      ref={containerRef}
      className={`relative flex h-12 w-full items-center rounded-full border border-white/[0.08] bg-black/32 p-1 select-none overflow-hidden ${
        disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"
      } ${className}`}
    >
      {/* Premium glowing fill trail */}
      <div
        className="absolute left-0 top-0 bottom-0 rounded-full bg-gradient-to-r from-cyan/10 to-cyan/35 transition-all duration-75"
        style={{width: `${dragX + 44}px`}}
      />

      {/* Label Text */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none px-12">
        <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
          {isLoading ? (
            <span className="flex items-center gap-2 text-cyan">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Processing...
            </span>
          ) : progressPercent > 80 ? (
            <span className="text-cyan animate-pulse">{activeLabel}</span>
          ) : (
            label
          )}
        </span>
      </div>

      {/* Draggable Knob */}
      <div
        ref={handleRef}
        onMouseDown={handleStart}
        onTouchStart={handleStart}
        className={`z-10 grid h-10 w-10 shrink-0 place-items-center rounded-full shadow-[0_4px_12px_rgba(0,0,0,0.3)] transition-colors duration-150 ${
          hasConfirmed
            ? "bg-teal text-white"
            : isDragging
              ? "bg-cyan-deep text-white cursor-grabbing"
              : "bg-cyan text-ink cursor-grab hover:bg-cyan-deep hover:text-white"
        }`}
        style={{
          transform: `translateX(${dragX}px)`,
          transition: isDragging ? "none" : "transform 250ms cubic-bezier(0.25, 1, 0.5, 1), background-color 150ms ease",
        }}
      >
        {isLoading || hasConfirmed ? (
          <Loader2 className="h-4 w-4 animate-spin text-white" />
        ) : (
          <ChevronRight className={`h-4 w-4 transition-transform duration-150 ${isDragging ? "scale-110" : ""}`} />
        )}
      </div>
    </div>
  );
}
