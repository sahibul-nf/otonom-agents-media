"use client";

import {useCallback, useEffect, useMemo, useState} from "react";

export function useReviewSelection(selectableIds: string[], resetKey: string) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setSelectedIds(new Set());
  }, [resetKey]);

  const selectableSet = useMemo(() => new Set(selectableIds), [selectableIds]);

  const toggle = useCallback(
    (id: string) => {
      if (!selectableSet.has(id)) return;
      setSelectedIds((current) => {
        const next = new Set(current);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
    },
    [selectableSet],
  );

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(selectableIds));
  }, [selectableIds]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const deselect = useCallback((id: string) => {
    setSelectedIds((current) => {
      if (!current.has(id)) return current;
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  }, []);

  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id));
  const someSelected = selectedIds.size > 0;

  return {
    selectedIds,
    selectedCount: selectedIds.size,
    isSelected: (id: string) => selectedIds.has(id),
    toggle,
    deselect,
    selectAll,
    clearSelection,
    allSelected,
    someSelected,
    selectableCount: selectableIds.length,
  };
}
