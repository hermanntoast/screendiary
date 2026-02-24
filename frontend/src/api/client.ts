import type {
  DateEntry,
  TimelineResponse,
  ScreenshotDetail,
  OcrWordsResponse,
  SearchResponse,
} from "../types";

export async function fetchDates(): Promise<DateEntry[]> {
  const resp = await fetch("/api/dates");
  return resp.json();
}

export async function fetchTimeline(date: string): Promise<TimelineResponse> {
  const resp = await fetch(
    `/api/timeline?date=${encodeURIComponent(date)}`
  );
  return resp.json();
}

export async function fetchScreenshotDetail(
  id: number
): Promise<ScreenshotDetail> {
  const resp = await fetch(`/api/screenshots/${id}`);
  return resp.json();
}

export async function fetchOcrWords(
  id: number,
  query: string
): Promise<OcrWordsResponse> {
  const resp = await fetch(
    `/api/screenshots/${id}/ocr-words?q=${encodeURIComponent(query)}`
  );
  return resp.json();
}

export async function fetchAllOcrWords(
  id: number
): Promise<OcrWordsResponse> {
  const resp = await fetch(`/api/screenshots/${id}/ocr-words`);
  return resp.json();
}

export async function fetchSearchText(
  query: string,
  limit = 100
): Promise<SearchResponse> {
  const resp = await fetch(
    `/api/search/text?q=${encodeURIComponent(query)}&limit=${limit}`
  );
  return resp.json();
}

export function screenshotImageUrl(id: number, monitor: number): string {
  return `/screenshots/${id}/image?monitor=${monitor}`;
}

export interface ActivitySummary {
  date: string;
  total_seconds: number;
  interval: number;
  top_apps: {
    app_class: string;
    app_name: string;
    count: number;
    seconds: number;
  }[];
  top_titles: {
    window_title: string;
    app_class: string;
    count: number;
    seconds: number;
  }[];
  top_domains: {
    browser_domain: string;
    count: number;
    seconds: number;
  }[];
  timeline: {
    timestamp: string;
    app_class: string;
    window_title: string;
  }[];
}

export async function fetchActivitySummary(
  date: string
): Promise<ActivitySummary> {
  const resp = await fetch(
    `/api/activity/summary?date=${encodeURIComponent(date)}`
  );
  return resp.json();
}

// --- Day Summary (new activity time tracking) ---

export interface DaySession {
  app_class: string;
  category: string;
  start: string;
  end: string;
  duration_seconds: number;
  window_titles: string[];
  browser_domains: string[];
  event_count: number;
}

export interface DayBreak {
  start: string;
  end: string;
  duration_seconds: number;
}

export interface DayMetrics {
  total_active_seconds: number;
  first_activity: string;
  last_activity: string;
  total_break_seconds: number;
  break_count: number;
  category_seconds: Record<string, number>;
}

export interface AIBlock {
  time_range: string;
  duration_minutes?: number;
  label: string;
  description: string;
  category: string;
}

export interface AISummary {
  summary: string;
  blocks: AIBlock[];
}

export interface DaySummaryResponse {
  date: string;
  sessions: DaySession[];
  metrics: DayMetrics;
  breaks: DayBreak[];
  ai_summary: AISummary | null;
  motd: string | null;
}

// --- MOTD ---

export interface MotdResponse {
  motd: string | null;
  date: string;
}

export async function fetchMotd(): Promise<MotdResponse> {
  const resp = await fetch("/api/activity/motd");
  return resp.json();
}

export async function fetchDaySummary(
  date: string,
  regenerate = false
): Promise<DaySummaryResponse> {
  const resp = await fetch(
    `/api/activity/day-summary?date=${encodeURIComponent(date)}&regenerate=${regenerate}`
  );
  return resp.json();
}

// --- Storage Stats ---

export interface StorageStats {
  total_screenshots: number;
  live_screenshots: number;
  archived_screenshots: number;
  ocr_results: number;
  embeddings: number;
  video_segments: number;
  storage_bytes: number;
  storage_gb: number;
  max_storage_gb: number;
  db_size_bytes: number;
  total_days: number;
  first_date: string | null;
  last_date: string | null;
}

export async function fetchStorageStats(): Promise<StorageStats> {
  const resp = await fetch("/api/stats");
  return resp.json();
}

// --- AI Chat SSE Stream ---

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export async function streamAiChat(
  query: string,
  history: ChatMessage[],
  onToken: (token: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): Promise<void> {
  const resp = await fetch("/api/search/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, history }),
  });

  if (!resp.ok || !resp.body) {
    onError(`HTTP ${resp.status}`);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data: ")) continue;
      const payload = trimmed.slice(6);

      if (payload === "[DONE]") {
        onDone();
        return;
      }

      try {
        const parsed = JSON.parse(payload);
        if (parsed.error) {
          onError(parsed.error);
          return;
        }
        if (parsed.content) {
          onToken(parsed.content);
        }
      } catch {
        // ignore malformed JSON
      }
    }
  }

  onDone();
}
