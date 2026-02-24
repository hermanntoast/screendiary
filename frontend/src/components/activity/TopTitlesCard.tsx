import { appColor, formatDuration } from "./utils";

interface TitleEntry {
  window_title: string;
  app_class: string;
  count: number;
  seconds: number;
}

interface Props {
  titles: TitleEntry[];
}

export function TopTitlesCard({ titles }: Props) {
  if (!titles.length) {
    return (
      <div className="activity-card">
        <h3 className="activity-card-title">Top Fenstertitel</h3>
        <div className="activity-card-empty">Keine Daten</div>
      </div>
    );
  }

  const maxCount = titles[0]!.count;

  return (
    <div className="activity-card">
      <h3 className="activity-card-title">Top Fenstertitel</h3>
      <div className="activity-card-list">
        {titles.map((t, i) => (
          <div key={i} className="activity-card-item">
            <div className="activity-card-item-header">
              <span
                className="activity-card-dot"
                style={{ backgroundColor: appColor(t.app_class) }}
              />
              <span className="activity-card-item-name activity-card-item-name-truncate">
                {t.window_title}
              </span>
              <span className="activity-card-item-time">
                {formatDuration(t.seconds)}
              </span>
            </div>
            <div className="activity-card-bar-bg">
              <div
                className="activity-card-bar-fill"
                style={{
                  width: `${(t.count / maxCount) * 100}%`,
                  backgroundColor: appColor(t.app_class),
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
