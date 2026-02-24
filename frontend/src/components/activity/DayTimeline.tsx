import { useMemo, useRef, useState } from "react";
import type { DaySession, DayBreak } from "../../api/client";
import { categoryColor } from "./CategoryColors";
import { formatDuration } from "./utils";

interface Props {
  sessions: DaySession[];
  breaks: DayBreak[];
  firstActivity: string;
  lastActivity: string;
}

export function DayTimeline({ sessions, breaks, firstActivity, lastActivity }: Props) {
  const barRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{
    text: string;
    left: number;
  } | null>(null);

  const { blocks, hourMarkers } = useMemo(() => {
    if (!sessions.length || !firstActivity || !lastActivity) {
      return { blocks: [], hourMarkers: [] };
    }

    const start = new Date(firstActivity).getTime();
    const end = new Date(lastActivity).getTime();
    const total = end - start;
    if (total <= 0) return { blocks: [], hourMarkers: [] };

    // Session blocks
    const sessionBlocks = sessions.map((s) => {
      const sStart = new Date(s.start).getTime();
      const sEnd = new Date(s.end).getTime();
      return {
        type: "session" as const,
        leftPct: ((sStart - start) / total) * 100,
        widthPct: Math.max(((sEnd - sStart) / total) * 100, 0.15),
        color: categoryColor(s.category),
        label: s.app_class,
        tooltip: `${s.app_class} (${formatTime(s.start)}–${formatTime(s.end)}) ${formatDuration(s.duration_seconds)}`,
        category: s.category,
      };
    });

    // Break blocks (dark gaps)
    const breakBlocks = breaks.map((b) => {
      const bStart = new Date(b.start).getTime();
      const bEnd = new Date(b.end).getTime();
      return {
        type: "break" as const,
        leftPct: ((bStart - start) / total) * 100,
        widthPct: ((bEnd - bStart) / total) * 100,
        color: "rgba(255,255,255,0.03)",
        label: "",
        tooltip: `Pause (${formatTime(b.start)}–${formatTime(b.end)}) ${formatDuration(b.duration_seconds)}`,
        category: "break",
      };
    });

    // Hour markers
    const firstHour = new Date(firstActivity);
    firstHour.setMinutes(0, 0, 0);
    if (firstHour.getTime() < start) firstHour.setHours(firstHour.getHours() + 1);

    const markers: { pct: number; label: string }[] = [];
    const h = new Date(firstHour);
    while (h.getTime() <= end) {
      const pct = ((h.getTime() - start) / total) * 100;
      if (pct >= 0 && pct <= 100) {
        markers.push({
          pct,
          label: h.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }),
        });
      }
      h.setHours(h.getHours() + 1);
    }

    return {
      blocks: [...sessionBlocks, ...breakBlocks],
      hourMarkers: markers,
    };
  }, [sessions, breaks, firstActivity, lastActivity]);

  if (!blocks.length) {
    return <div className="activity-timeline-empty">Keine Timeline-Daten</div>;
  }

  return (
    <div className="activity-day-timeline">
      {/* Hour markers */}
      <div className="activity-day-timeline-hours">
        {hourMarkers.map((m) => (
          <div
            key={m.label}
            className="activity-day-timeline-hour"
            style={{ left: `${m.pct}%` }}
          >
            <span className="activity-day-timeline-hour-label">{m.label}</span>
          </div>
        ))}
      </div>

      {/* Main bar */}
      <div
        ref={barRef}
        className="activity-day-timeline-bar"
        onMouseLeave={() => setTooltip(null)}
      >
        {blocks.map((block, i) => (
          <div
            key={i}
            className={`activity-day-timeline-block ${block.type === "break" ? "is-break" : ""}`}
            style={{
              left: `${block.leftPct}%`,
              width: `${Math.max(block.widthPct, 0.15)}%`,
              backgroundColor: block.color,
            }}
            onMouseEnter={(e) => {
              const rect = barRef.current!.getBoundingClientRect();
              setTooltip({ text: block.tooltip, left: e.clientX - rect.left });
            }}
            onMouseMove={(e) => {
              const rect = barRef.current!.getBoundingClientRect();
              setTooltip((prev) =>
                prev ? { ...prev, left: e.clientX - rect.left } : prev
              );
            }}
          >
            {block.type === "session" && block.widthPct > 3 && (
              <span className="activity-day-timeline-block-label">
                {block.label}
              </span>
            )}
          </div>
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
    </div>
  );
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
