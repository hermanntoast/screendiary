import { formatDuration } from "./utils";

interface DomainEntry {
  browser_domain: string;
  count: number;
  seconds: number;
}

interface Props {
  domains: DomainEntry[];
}

export function TopDomainsCard({ domains }: Props) {
  if (!domains.length) {
    return (
      <div className="activity-card">
        <h3 className="activity-card-title">Top Browser-Domains</h3>
        <div className="activity-card-empty">Keine Daten</div>
      </div>
    );
  }

  const maxCount = domains[0]!.count;

  return (
    <div className="activity-card">
      <h3 className="activity-card-title">Top Browser-Domains</h3>
      <div className="activity-card-list">
        {domains.map((d) => (
          <div key={d.browser_domain} className="activity-card-item">
            <div className="activity-card-item-header">
              <span className="activity-card-dot activity-card-dot-domain" />
              <span className="activity-card-item-name">
                {d.browser_domain}
              </span>
              <span className="activity-card-item-time">
                {formatDuration(d.seconds)}
              </span>
            </div>
            <div className="activity-card-bar-bg">
              <div
                className="activity-card-bar-fill activity-card-bar-domain"
                style={{
                  width: `${(d.count / maxCount) * 100}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
