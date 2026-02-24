import type { DateEntry } from "../../types";
import { formatDuration } from "./utils";

interface Props {
  dates: DateEntry[];
  selectedDate: string;
  totalSeconds: number;
  onDateChange: (date: string) => void;
}

export function ActivityHeader({
  dates,
  selectedDate,
  totalSeconds,
  onDateChange,
}: Props) {
  return (
    <div className="activity-header">
      <div className="activity-header-left">
        <h1 className="activity-title">Aktivitaeten</h1>
        <span className="activity-total-time">
          {formatDuration(totalSeconds)} erfasst
        </span>
      </div>
      <select
        className="activity-date-select"
        value={selectedDate}
        onChange={(e) => onDateChange(e.target.value)}
      >
        {dates.map((d) => (
          <option key={d.date} value={d.date}>
            {d.date}
          </option>
        ))}
      </select>
    </div>
  );
}
