import { useState } from "react";
import type { DaySession, DayBreak } from "../../api/client";
import { categoryColor, categoryLabel } from "./CategoryColors";
import { formatDuration } from "./utils";

interface Props {
  sessions: DaySession[];
  breaks: DayBreak[];
}

interface TimelineItem {
  type: "session" | "break";
  start: string;
  end: string;
  session?: DaySession;
  breakData?: DayBreak;
}

export function SessionList({ sessions, breaks }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (!sessions.length) return null;

  // Merge sessions and breaks into chronological list
  const items: TimelineItem[] = [];
  for (const s of sessions) {
    items.push({ type: "session", start: s.start, end: s.end, session: s });
  }
  for (const b of breaks) {
    items.push({ type: "break", start: b.start, end: b.end, breakData: b });
  }
  items.sort((a, b) => a.start.localeCompare(b.start));

  return (
    <div className="activity-session-list">
      <h3 className="activity-card-title">Sessions</h3>
      <div className="activity-session-items">
        {items.map((item, i) => {
          if (item.type === "break" && item.breakData) {
            return (
              <div key={`b-${i}`} className="activity-session-item is-break">
                <span className="activity-session-time">
                  {formatTime(item.start)} – {formatTime(item.end)}
                </span>
                <span className="activity-session-name">Pause</span>
                <span className="activity-session-duration">
                  {formatDuration(item.breakData.duration_seconds)}
                </span>
              </div>
            );
          }

          const s = item.session!;
          const isExpanded = expandedIdx === i;

          return (
            <div key={`s-${i}`} className="activity-session-item-wrap">
              <div
                className={`activity-session-item ${isExpanded ? "is-expanded" : ""}`}
                onClick={() => setExpandedIdx(isExpanded ? null : i)}
              >
                <span className="activity-session-time">
                  {formatTime(s.start)} – {formatTime(s.end)}
                </span>
                <span
                  className="activity-session-badge"
                  style={{ backgroundColor: categoryColor(s.category) }}
                >
                  {categoryLabel(s.category)}
                </span>
                <span className="activity-session-name">{s.app_class}</span>
                <span className="activity-session-duration">
                  {formatDuration(s.duration_seconds)}
                </span>
                <span className="activity-session-chevron">
                  {isExpanded ? "▾" : "▸"}
                </span>
              </div>
              {isExpanded && (
                <div className="activity-session-details">
                  {s.window_titles.length > 0 && (
                    <div className="activity-session-detail-group">
                      <span className="activity-session-detail-label">Fenster:</span>
                      <ul className="activity-session-detail-list">
                        {s.window_titles.map((t, j) => (
                          <li key={j}>{t}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {s.browser_domains.length > 0 && (
                    <div className="activity-session-detail-group">
                      <span className="activity-session-detail-label">Domains:</span>
                      <ul className="activity-session-detail-list">
                        {s.browser_domains.map((d, j) => (
                          <li key={j}>{d}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="activity-session-detail-meta">
                    {s.event_count} Events
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
