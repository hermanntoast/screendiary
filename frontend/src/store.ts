import { create } from "zustand";
import type {
  DateEntry,
  TimelineEntry,
  SearchResult,
  ScreenshotDetail,
} from "./types";
import {
  fetchDates,
  fetchTimeline,
  fetchScreenshotDetail,
  fetchSearchText,
  fetchOcrWords,
} from "./api/client";

interface PlayerState {
  // Data
  dates: DateEntry[];
  selectedDate: string;
  entries: TimelineEntry[];
  currentIndex: number;
  monitorCount: number;
  focusedMonitor: number; // -1 = show all

  // Search
  searchQuery: string;
  activeSearchQuery: string;
  searchResults: SearchResult[];
  searchHitIndices: Set<number>;
  showSearchDropdown: boolean;

  // Caches
  imageCache: Map<string, HTMLImageElement>;
  monitorInfoCache: Map<number, ScreenshotDetail>;

  // Actions
  loadDates: () => Promise<void>;
  loadDate: (date: string) => Promise<void>;
  setSelectedDate: (date: string) => void;
  goTo: (index: number) => void;
  focusMonitor: (index: number) => void;
  unfocusMonitor: () => void;
  setSearchQuery: (query: string) => void;
  executeSearch: (query: string) => Promise<void>;
  clearSearch: () => void;
  jumpToScreenshot: (id: number, date: string) => Promise<void>;
  setShowSearchDropdown: (show: boolean) => void;
  preloadAround: (index: number) => void;
}

const PRELOAD_AHEAD = 3;
const PRELOAD_BEHIND = 1;

export const useStore = create<PlayerState>((set, get) => ({
  dates: [],
  selectedDate: "",
  entries: [],
  currentIndex: -1,
  monitorCount: 0,
  focusedMonitor: -1,

  searchQuery: "",
  activeSearchQuery: "",
  searchResults: [],
  searchHitIndices: new Set(),
  showSearchDropdown: false,

  imageCache: new Map(),
  monitorInfoCache: new Map(),

  loadDates: async () => {
    const dates = await fetchDates();
    if (!dates.length) return;
    set({ dates });
    const today = new Date().toISOString().slice(0, 10);
    const defaultDate = dates.some((d) => d.date === today)
      ? today
      : dates[0]!.date;
    await get().loadDate(defaultDate);
  },

  loadDate: async (date: string) => {
    if (!date) return;
    const { activeSearchQuery } = get();

    set({
      selectedDate: date,
      entries: [],
      currentIndex: -1,
      focusedMonitor: -1,
      imageCache: new Map(),
      monitorInfoCache: new Map(),
      searchHitIndices: new Set(),
    });

    const data = await fetchTimeline(date);
    const entries = data.entries || [];
    if (!entries.length) {
      set({ entries });
      return;
    }

    // Determine monitor count from first entry
    let monitorCount = 1;
    try {
      const info = await fetchScreenshotDetail(entries[0]!.id);
      monitorCount = info.monitors.length || 1;
      get().monitorInfoCache.set(entries[0]!.id, info);
    } catch {
      // fallback to 1
    }

    set({ entries, monitorCount });
    get().goTo(entries.length - 1);

    // Re-apply search if active
    if (activeSearchQuery) {
      await get().executeSearch(activeSearchQuery);
    }
  },

  setSelectedDate: (date: string) => set({ selectedDate: date }),

  goTo: (index: number) => {
    const { entries } = get();
    if (index < 0 || index >= entries.length) return;
    set({ currentIndex: index });
    get().preloadAround(index);
  },

  focusMonitor: (index: number) => {
    const { monitorCount } = get();
    if (index < 0 || index >= monitorCount) return;
    set({ focusedMonitor: index });
  },

  unfocusMonitor: () => set({ focusedMonitor: -1 }),

  setSearchQuery: (query: string) => set({ searchQuery: query }),

  executeSearch: async (query: string) => {
    set({ activeSearchQuery: query });
    try {
      const data = await fetchSearchText(query);
      const results = data.results;
      const { entries } = get();

      // Build set of hit indices on the timeline
      const hitIds = new Set(results.map((r) => r.screenshot_id));
      const hitIndices = new Set<number>();
      entries.forEach((e, i) => {
        if (hitIds.has(e.id)) hitIndices.add(i);
      });

      set({
        searchResults: results,
        searchHitIndices: hitIndices,
        showSearchDropdown: true,
      });
    } catch {
      set({ searchResults: [], searchHitIndices: new Set() });
    }
  },

  clearSearch: () =>
    set({
      activeSearchQuery: "",
      searchQuery: "",
      searchResults: [],
      searchHitIndices: new Set(),
      showSearchDropdown: false,
    }),

  jumpToScreenshot: async (id: number, date: string) => {
    const state = get();

    // Switch date if needed
    if (date && date !== state.selectedDate) {
      await state.loadDate(date);
    }

    const { entries, activeSearchQuery, monitorCount } = get();
    const idx = entries.findIndex((e) => e.id === id);
    if (idx >= 0) get().goTo(idx);

    // Focus on the monitor with the matching text
    if (activeSearchQuery && monitorCount > 1) {
      try {
        const data = await fetchOcrWords(id, activeSearchQuery);
        if (data.monitors) {
          for (const mon of data.monitors) {
            if (mon.words.some((w) => w.matched)) {
              get().focusMonitor(mon.monitor_index);
              return;
            }
          }
        }
      } catch {
        // ignore
      }
    }
  },

  setShowSearchDropdown: (show: boolean) =>
    set({ showSearchDropdown: show }),

  preloadAround: (idx: number) => {
    const { entries, monitorCount, imageCache } = get();
    for (let i = idx - PRELOAD_BEHIND; i <= idx + PRELOAD_AHEAD; i++) {
      if (i < 0 || i >= entries.length) continue;
      const entry = entries[i]!;
      for (let m = 0; m < monitorCount; m++) {
        const key = `${entry.id}:${m}`;
        if (imageCache.has(key)) continue;
        const pre = new Image();
        pre.src = `/screenshots/${entry.id}/image?monitor=${m}`;
        imageCache.set(key, pre);
      }
    }
    // Trim cache if too large
    if (imageCache.size > 50 * monitorCount) {
      for (const [key] of imageCache) {
        const id = parseInt(key.split(":")[0]!);
        const ei = entries.findIndex((e) => e.id === id);
        if (ei === -1 || Math.abs(ei - idx) > 10) imageCache.delete(key);
        if (imageCache.size <= 30 * monitorCount) break;
      }
    }
  },
}));
