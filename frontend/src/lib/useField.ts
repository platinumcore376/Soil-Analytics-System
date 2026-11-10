'use client';

/* Reads the field chosen on the Home screen. Returns null until mounted so server and
 * client render agree — localStorage is unavailable during SSR. */

import { useEffect, useState } from 'react';

export interface SelectedField {
  fieldId: number;
  fieldName: string;
  farmName: string;
  areaHectares: number | null;
}

export const FIELD_KEY = 'soil-health-field';

export function useField(): { field: SelectedField | null; ready: boolean } {
  const [field, setField] = useState<SelectedField | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(FIELD_KEY);
      if (raw) setField(JSON.parse(raw) as SelectedField);
    } catch {
      /* Corrupt value — treat as no selection rather than crashing the screen. */
    }
    setReady(true);
  }, []);

  return { field, ready };
}
