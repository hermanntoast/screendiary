export interface DateEntry {
  date: string;
  count: number;
}

export interface TimelineEntry {
  id: number;
  timestamp: string;
  date: string;
}

export interface MonitorInfo {
  id: number;
  monitor_name: string;
  monitor_index: number;
  width: number;
  height: number;
  image_url: string;
}

export interface ScreenshotDetail {
  id: number;
  timestamp: string;
  date: string;
  width: number;
  height: number;
  file_size: number;
  storage_type: string;
  monitors: MonitorInfo[];
  ocr_text: string;
}

export interface OcrWord {
  word: string;
  left: number;
  top: number;
  width: number;
  height: number;
  confidence: number;
  matched: boolean;
}

export interface OcrMonitor {
  monitor_capture_id: number;
  monitor_index: number;
  monitor_name: string;
  words: OcrWord[];
}

export interface OcrWordsResponse {
  screenshot_id: number;
  query: string;
  monitors: OcrMonitor[];
}

export interface SearchResult {
  screenshot_id: number;
  timestamp: string;
  date: string;
  score: number;
  highlights: string[];
  ocr_text: string;
  thumb_url: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

export interface TimelineResponse {
  date: string;
  entries: TimelineEntry[];
  count: number;
}
