import { useMemo, useState } from "react";
import { appColor } from "./utils";

interface TimelineEntry {
  timestamp: string;
  app_class: string;
  window_title: string;
}

interface Props {
  timeline: TimelineEntry[];
}

interface Segment {
  app_class: string;
  startPct: number;
  widthPct: number;
  startTime: string;
  endTime: string;
  title: string;
}

export function ActivityTimeline({ timeline }: Props) {
  const [tooltip, setTooltip] = useState<{
    text: string;
    left: number;
  } | null>(null);

  const segments = useMemo(() => {
    if (timeline.length < 2) return [];

    const first = new Date(timeline[0]!.timestamp).getTime();
    const last = new Date(timeline[timeline.length - 1]!.timestamp).getTime();
    const totalMs = last - first;
    if (totalMs <= 0) return [];

    // Merge consecutive entries with same app_class into segments
    const merged: Segment[] = [];
    let current = timeline[0]!;
    let segStart = first;

    for (let i = 1; i < timeline.length; i++) {
      const entry = timeline[i]!;
      if (entry.app_class !== current.app_class) {
        const entryTime = new Date(entry.timestamp).getTime();
        merged.push({
          app_class: current.app_class,
          startPct: ((segStart - first) / totalMs) * 100,
          widthPct: ((entryTime - segStart) / totalMs) * 100,
          startTime: new Date(segStart).toLocaleTimeString("de-DE", {
            hour: "2-digit",
            minute: "2-digit",
          }),
          endTime: new Date(entryTime).toLocaleTimeString("de-DE", {
            hour: "2-digit",
            minute: "2-digit",
          }),
          title: current.window_title,
        });
        current = entry;
        segStart = entryTime;
      }
    }
    // Last segment
    merged.push({
      app_class: current.app_class,
      startPct: ((segStart - first) / totalMs) * 100,
      widthPct: ((last - segStart) / totalMs) * 100,
      startTime: new Date(segStart).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
      }),
      endTime: new Date(last).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
      }),
      title: current.window_title,
    });

    return merged;
  }, [timeline]);

  if (!segments.length) {
    return (
      <div className="activity-timeline-empty">Keine Timeline-Daten</div>
    );
  }

  // Time labels
  const firstTime = new Date(timeline[0]!.timestamp);
  const lastTime = new Date(timeline[timeline.length - 1]!.timestamp);

  return (
    <div className="activity-timeline-wrap">
      <div
        className="activity-timeline-bar"
        onMouseLeave={() => setTooltip(null)}
      >
        {segments.map((seg, i) => (
          <div
            key={i}
            className="activity-timeline-segment"
            style={{
              left: `${seg.startPct}%`,
              width: `${Math.max(seg.widthPct, 0.2)}%`,
              backgroundColor: appColor(seg.app_class),
            }}
            onMouseEnter={(e) => {
              const rect = e.currentTarget
                .closest(".activity-timeline-bar")!
                .getBoundingClientRect();
              setTooltip({
                text: `${seg.app_class || "unbekannt"} (${seg.startTime}–${seg.endTime})`,
                left: e.clientX - rect.left,
              });
            }}
            onMouseMove={(e) => {
              const rect = e.currentTarget
                .closest(".activity-timeline-bar")!
                .getBoundingClientRect();
              setTooltip((prev) =>
                prev ? { ...prev, left: e.clientX - rect.left } : prev
              );
            }}
          />
        ))}
        {tooltip && (
          <div
            className="activity-timeline-tooltip"
            style={{ left: `${tooltip.left}px` }}
          >
            {tooltip.text}
          </div>
        )}
      </div>
      <div className="activity-timeline-labels">
        <span>
          {firstTime.toLocaleTimeString("de-DE", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
        <span>
          {lastTime.toLocaleTimeString("de-DE", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}
