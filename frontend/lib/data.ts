"use client";

import { useState, useEffect } from "react";
import type { BatchReport, NoteData } from "./types";

interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function useFetchData<T>(url: string): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(url);
        if (!res.ok) {
          throw new Error(`Failed to load ${url}: ${res.status} ${res.statusText}`);
        }
        const json = (await res.json()) as T;
        if (!cancelled) {
          setState({ data: json, loading: false, error: null });
        }
      } catch (err) {
        if (!cancelled) {
          setState({
            data: null,
            loading: false,
            error: err instanceof Error ? err.message : "Unknown error",
          });
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [url]);

  return state;
}

export function useResults(): FetchState<BatchReport> {
  return useFetchData<BatchReport>("/data/results.json");
}

export function useNotes(): FetchState<NoteData[]> {
  return useFetchData<NoteData[]>("/data/notes.json");
}
