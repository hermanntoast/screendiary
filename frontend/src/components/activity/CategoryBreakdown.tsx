import { categoryColor, categoryLabel } from "./CategoryColors";
import { formatDuration } from "./utils";

interface Props {
  categorySeconds: Record<string, number>;
}

export function CategoryBreakdown({ categorySeconds }: Props) {
  const entries = Object.entries(categorySeconds)
    .filter(([, secs]) => secs > 0)
    .sort(([, a], [, b]) => b - a);

  if (!entries.length) return null;

  const total = entries.reduce((sum, [, s]) => sum + s, 0);

  return (
    <div className="activity-category-breakdown">
      <h3 className="activity-card-title">Kategorien</h3>

      {/* Stacked bar */}
      <div className="activity-category-bar">
        {entries.map(([cat, secs]) => (
          <div
            key={cat}
            className="activity-category-bar-segment"
            style={{
              width: `${(secs / total) * 100}%`,
              backgroundColor: categoryColor(cat),
            }}
            title={`${categoryLabel(cat)}: ${formatDuration(secs)}`}
          >
            {secs / total > 0.08 && (
              <span className="activity-category-bar-label">
                {formatDuration(secs)}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="activity-category-legend">
        {entries.map(([cat, secs]) => (
          <div key={cat} className="activity-category-legend-item">
            <span
              className="activity-category-legend-dot"
              style={{ backgroundColor: categoryColor(cat) }}
            />
            <span className="activity-category-legend-name">
              {categoryLabel(cat)}
            </span>
            <span className="activity-category-legend-time">
              {formatDuration(secs)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
