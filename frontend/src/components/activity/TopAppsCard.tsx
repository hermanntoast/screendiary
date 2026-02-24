import { appColor, formatDuration } from "./utils";

interface AppEntry {
  app_class: string;
  app_name: string;
  count: number;
  seconds: number;
}

interface Props {
  apps: AppEntry[];
}

export function TopAppsCard({ apps }: Props) {
  if (!apps.length) {
    return (
      <div className="activity-card">
        <h3 className="activity-card-title">Top Anwendungen</h3>
        <div className="activity-card-empty">Keine Daten</div>
      </div>
    );
  }

  const maxCount = apps[0]!.count;

  return (
    <div className="activity-card">
      <h3 className="activity-card-title">Top Anwendungen</h3>
      <div className="activity-card-list">
        {apps.map((app) => (
          <div key={app.app_class} className="activity-card-item">
            <div className="activity-card-item-header">
              <span
                className="activity-card-dot"
                style={{ backgroundColor: appColor(app.app_class) }}
              />
              <span className="activity-card-item-name">
                {app.app_class || "unbekannt"}
              </span>
              <span className="activity-card-item-time">
                {formatDuration(app.seconds)}
              </span>
            </div>
            <div className="activity-card-bar-bg">
              <div
                className="activity-card-bar-fill"
                style={{
                  width: `${(app.count / maxCount) * 100}%`,
                  backgroundColor: appColor(app.app_class),
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
