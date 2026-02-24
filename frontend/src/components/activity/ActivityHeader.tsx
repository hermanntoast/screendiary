import type { DateEntry } from "../../types";

interface Props {
  dates: DateEntry[];
  selectedDate: string;
  onDateChange: (date: string) => void;
}

export function ActivityHeader({
  dates,
  selectedDate,
  onDateChange,
}: Props) {
  return (
    <div className="activity-header">
      <h1 className="activity-title">Aktivitaeten</h1>
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
