import { useState, useEffect } from "react";
import { fetchStorageStats, type StorageStats } from "../../api/client";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
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
