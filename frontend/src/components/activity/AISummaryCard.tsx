import type { AISummary } from "../../api/client";
import { categoryColor } from "./CategoryColors";

interface Props {
  aiSummary: AISummary | null;
  motd: string | null;
  onRegenerate: () => void;
  loading: boolean;
}

function formatBlockDuration(minutes?: number): string {
  if (!minutes) return "";
  if (minutes >= 60) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  return `${minutes}m`;
}

export function AISummaryCard({ aiSummary, motd, onRegenerate, loading }: Props) {
  // No summary yet — show generate button
  if (!aiSummary) {
    return (
      <div className="activity-card activity-ai-card">
        <div className="activity-ai-generate-prompt">
          <button
            className="activity-ai-generate-btn"
            onClick={onRegenerate}
            disabled={loading}
          >
            {loading ? "Generiere Zeiterfassung..." : "Tag zusammenfassen"}
          </button>
          <span className="activity-ai-generate-hint">
            KI fasst den Tag in Zeiterfassungsbloecke zusammen
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="activity-card activity-ai-card">
      <div className="activity-ai-header">
        <h3 className="activity-card-title">Zeiterfassung</h3>
        <button
          className="activity-ai-regen"
          onClick={onRegenerate}
          disabled={loading}
        >
          {loading ? "Generiere..." : "Neu generieren"}
        </button>
      </div>

      {motd && <p className="activity-ai-motd">{motd}</p>}

      <p className="activity-ai-summary">{aiSummary.summary}</p>

      {aiSummary.blocks?.length > 0 && (
        <div className="activity-ai-blocks">
          {aiSummary.blocks.map((block, i) => (
            <div key={i} className="activity-ai-block">
              <span className="activity-ai-block-time">
                {block.time_range}
              </span>
              {block.category !== "pause" && (
                <span
                  className="activity-ai-block-dot"
                  style={{ backgroundColor: categoryColor(block.category) }}
                />
              )}
              {block.category === "pause" && (
                <span className="activity-ai-block-dot activity-ai-block-dot-pause" />
              )}
              <div className="activity-ai-block-content">
                <div className="activity-ai-block-top">
                  <span className="activity-ai-block-label">{block.label}</span>
                  {block.duration_minutes && (
                    <span className="activity-ai-block-duration">
                      {formatBlockDuration(block.duration_minutes)}
                    </span>
                  )}
                </div>
                <span className="activity-ai-block-desc">{block.description}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
