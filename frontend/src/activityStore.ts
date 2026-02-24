import { create } from "zustand";
import {
  fetchDates,
  fetchActivitySummary,
  fetchDaySummary,
  fetchMotd,
  type ActivitySummary,
  type DaySummaryResponse,
} from "./api/client";
import type { DateEntry } from "./types";

interface ActivityState {
  dates: DateEntry[];
  selectedDate: string;
  summary: ActivitySummary | null;
  daySummary: DaySummaryResponse | null;
  loading: boolean;
  daySummaryLoading: boolean;
  motd: string | null;

  loadDates: () => Promise<void>;
  loadActivity: (date: string) => Promise<void>;
  loadDaySummary: (date: string, regenerate?: boolean) => Promise<void>;
  setSelectedDate: (date: string) => void;
}

export const useActivityStore = create<ActivityState>((set, get) => ({
  dates: [],
  selectedDate: "",
  summary: null,
  daySummary: null,
  loading: false,
  daySummaryLoading: false,
  motd: null,

  loadDates: async () => {
    const dates = await fetchDates();
    if (!dates.length) return;
    set({ dates });
    const today = new Date().toISOString().slice(0, 10);
    const defaultDate = dates.some((d) => d.date === today)
      ? today
      : dates[0]!.date;
    // Load activity and MOTD in parallel
    const motdPromise = fetchMotd().then((r) => {
      if (r.motd) set({ motd: r.motd });
    }).catch(() => {});
    await Promise.all([get().loadActivity(defaultDate), motdPromise]);
  },

  loadActivity: async (date: string) => {
    if (!date) return;
    set({ selectedDate: date, loading: true });
    try {
      const [summary, daySummary] = await Promise.all([
        fetchActivitySummary(date),
        fetchDaySummary(date),
      ]);
      set({ summary, daySummary, loading: false });
    } catch {
      set({ summary: null, daySummary: null, loading: false });
    }
  },

  loadDaySummary: async (date: string, regenerate = false) => {
    if (!date) return;
    set({ daySummaryLoading: true });
    try {
      const daySummary = await fetchDaySummary(date, regenerate);
      set({ daySummary, daySummaryLoading: false });
    } catch {
      set({ daySummaryLoading: false });
    }
  },

  setSelectedDate: (date: string) => {
    set({ selectedDate: date });
    get().loadActivity(date);
  },
}));
