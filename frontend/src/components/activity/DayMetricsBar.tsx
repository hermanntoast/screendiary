import { formatDuration } from "./utils";

interface Props {
  totalActiveSeconds: number;
  breakCount: number;
  totalBreakSeconds: number;
  firstActivity: string;
  lastActivity: string;
}

export function DayMetricsBar({
  totalActiveSeconds,
  breakCount,
  totalBreakSeconds,
  firstActivity,
  lastActivity,
}: Props) {
  if (!totalActiveSeconds) return null;

  const firstTime = firstActivity
    ? new Date(firstActivity).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "–";
  const lastTime = lastActivity
    ? new Date(lastActivity).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "–";

  return (
    <div className="activity-metrics-bar">
      <div className="activity-metric">
        <span className="activity-metric-value">
          {formatDuration(totalActiveSeconds)}
        </span>
        <span className="activity-metric-label">Aktive Zeit</span>
      </div>
      <div className="activity-metric-sep" />
      <div className="activity-metric">
        <span className="activity-metric-value">
          {breakCount} Pausen ({formatDuration(totalBreakSeconds)})
        </span>
        <span className="activity-metric-label">Pausen</span>
      </div>
      <div className="activity-metric-sep" />
      <div className="activity-metric">
        <span className="activity-metric-value">
          {firstTime} – {lastTime}
        </span>
        <span className="activity-metric-label">Arbeitszeit</span>
      </div>
    </div>
  );
}
