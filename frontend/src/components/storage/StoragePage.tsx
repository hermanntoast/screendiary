import { useState, useEffect } from "react";
import { fetchStorageStats, type StorageStats } from "../../api/client";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatGb(gb: number): string {
  if (gb < 1) return `${(gb * 1024).toFixed(0)} MB`;
  return `${gb.toFixed(1)} GB`;
}

function formatDuration(days: number): string {
  if (days < 1) return "< 1 Tag";
  if (days < 30) return `${Math.round(days)} Tage`;
  const months = days / 30.44;
  if (months < 12) return `${months.toFixed(1)} Monate`;
  const years = days / 365.25;
  return `${years.toFixed(1)} Jahre`;
}

function StorageProjection({ stats }: { stats: StorageStats }) {
  const days = stats.total_days;
  if (days < 1 || stats.storage_bytes === 0) return null;

  const gbPerDay = stats.storage_gb / days;
  const screenshotsPerDay = stats.total_screenshots / days;
  const remainingGb = stats.max_storage_gb - stats.storage_gb;
  const daysRemaining = remainingGb > 0 ? remainingGb / gbPerDay : 0;

  const projections = [
    { label: "7 Tage", days: 7 },
    { label: "30 Tage", days: 30 },
    { label: "90 Tage", days: 90 },
    { label: "1 Jahr", days: 365 },
  ];

  return (
    <div className="storage-projection">
      <div className="storage-projection-title">Hochrechnung</div>
      <div className="storage-projection-basis">
        Basierend auf {days} Tagen Aufzeichnung ({stats.first_date} bis {stats.last_date})
      </div>

      <div className="storage-projection-metrics">
        <div className="storage-projection-metric">
          <span className="storage-projection-metric-value">{formatGb(gbPerDay)}</span>
          <span className="storage-projection-metric-label">pro Tag</span>
        </div>
        <div className="storage-projection-metric-sep" />
        <div className="storage-projection-metric">
          <span className="storage-projection-metric-value">{Math.round(screenshotsPerDay).toLocaleString()}</span>
          <span className="storage-projection-metric-label">Screenshots / Tag</span>
        </div>
        <div className="storage-projection-metric-sep" />
        <div className="storage-projection-metric">
          <span className="storage-projection-metric-value">{formatDuration(daysRemaining)}</span>
          <span className="storage-projection-metric-label">verbleibend</span>
        </div>
      </div>

      <div className="storage-projection-table">
        <div className="storage-projection-row storage-projection-header">
          <span>Zeitraum</span>
          <span>Speicher</span>
          <span>Gesamt</span>
          <span>Auslastung</span>
        </div>
        {projections.map((p) => {
          const projected = gbPerDay * p.days;
          const total = stats.storage_gb + projected;
          const pct = Math.min((total / stats.max_storage_gb) * 100, 100);
          const isOver = total > stats.max_storage_gb;
          return (
            <div key={p.label} className={`storage-projection-row ${isOver ? "storage-projection-row-over" : ""}`}>
              <span>{p.label}</span>
              <span className="storage-projection-mono">+{formatGb(projected)}</span>
              <span className="storage-projection-mono">{formatGb(total)}</span>
              <span>
                <span className="storage-projection-bar-bg">
                  <span
                    className={`storage-projection-bar-fill ${isOver ? "storage-projection-bar-danger" : ""}`}
                    style={{ width: `${pct}%` }}
                  />
                </span>
                <span className={`storage-projection-pct ${isOver ? "storage-projection-pct-over" : ""}`}>
                  {pct.toFixed(0)}%
                </span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function StoragePage() {
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStorageStats()
      .then(setStats)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="storage-page">
        <div className="activity-loading">Lade Speicherstatistiken...</div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="storage-page">
        <div className="activity-loading">Fehler beim Laden der Statistiken.</div>
      </div>
    );
  }

  const percentage = stats.max_storage_gb > 0
    ? Math.min((stats.storage_gb / stats.max_storage_gb) * 100, 100)
    : 0;

  const capacityClass =
    percentage > 95 ? "storage-capacity-fill storage-capacity-danger" :
    percentage > 80 ? "storage-capacity-fill storage-capacity-warning" :
    "storage-capacity-fill";

  return (
    <div className="storage-page">
      <h1 className="storage-title">Speicher</h1>

      {/* Capacity bar */}
      <div className="storage-capacity">
        <div className="storage-capacity-bar">
          <div className={capacityClass} style={{ width: `${percentage}%` }} />
        </div>
        <div className="storage-capacity-label">
          {stats.storage_gb.toFixed(2)} GB / {stats.max_storage_gb} GB ({percentage.toFixed(1)}%)
        </div>
      </div>

      {/* Overview grid */}
      <div className="storage-grid">
        <div className="storage-card">
          <div className="storage-card-value">{stats.total_screenshots.toLocaleString()}</div>
          <div className="storage-card-label">Screenshots</div>
          <div className="storage-card-detail">
            {stats.live_screenshots.toLocaleString()} live / {stats.archived_screenshots.toLocaleString()} archiviert
          </div>
        </div>
        <div className="storage-card">
          <div className="storage-card-value">{stats.video_segments.toLocaleString()}</div>
          <div className="storage-card-label">Video-Segmente</div>
        </div>
        <div className="storage-card">
          <div className="storage-card-value">{stats.ocr_results.toLocaleString()}</div>
          <div className="storage-card-label">OCR-Ergebnisse</div>
        </div>
        <div className="storage-card">
          <div className="storage-card-value">{stats.embeddings.toLocaleString()}</div>
          <div className="storage-card-label">Embeddings</div>
        </div>
      </div>

      {/* Storage projection */}
      <StorageProjection stats={stats} />

      {/* Storage details */}
      <div className="storage-details">
        <div className="storage-details-row">
          <span className="storage-details-label">Gesamtspeicher</span>
          <span className="storage-details-value">
            {stats.storage_gb.toFixed(2)} GB / {stats.max_storage_gb} GB
          </span>
        </div>
        <div className="storage-details-row">
          <span className="storage-details-label">Datenbank</span>
          <span className="storage-details-value">{formatBytes(stats.db_size_bytes)}</span>
        </div>
      </div>
    </div>
  );
}
