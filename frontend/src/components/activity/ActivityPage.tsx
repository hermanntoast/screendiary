import { useEffect } from "react";
import { useActivityStore } from "../../activityStore";
import { ActivityHeader } from "./ActivityHeader";
import { DayTimeline } from "./DayTimeline";
import { DayMetricsBar } from "./DayMetricsBar";
import { AISummaryCard } from "./AISummaryCard";
import { CategoryBreakdown } from "./CategoryBreakdown";
import { SessionList } from "./SessionList";
import { TopAppsCard } from "./TopAppsCard";
import { TopTitlesCard } from "./TopTitlesCard";
import { TopDomainsCard } from "./TopDomainsCard";

export function ActivityPage() {
  const {
    dates,
    selectedDate,
    summary,
    daySummary,
    loading,
    daySummaryLoading,
    motd,
    loadDates,
    loadDaySummary,
    setSelectedDate,
  } = useActivityStore();

  useEffect(() => {
    loadDates();
  }, [loadDates]);

  const handleRegenerate = () => {
    if (selectedDate) {
      loadDaySummary(selectedDate, true);
    }
  };

  return (
    <div className="activity-page">
      <ActivityHeader
        dates={dates}
        selectedDate={selectedDate}
        totalSeconds={summary?.total_seconds ?? 0}
        onDateChange={setSelectedDate}
      />

      {motd && (
        <div className="activity-motd">{motd}</div>
      )}

      {loading ? (
        <div className="activity-loading">Lade Aktivitaeten...</div>
      ) : summary ? (
        <>
          {/* New day timeline */}
          {daySummary && daySummary.sessions.length > 0 && (
            <>
              <DayTimeline
                sessions={daySummary.sessions}
                breaks={daySummary.breaks}
                firstActivity={daySummary.metrics.first_activity}
                lastActivity={daySummary.metrics.last_activity}
              />

              <DayMetricsBar
                totalActiveSeconds={daySummary.metrics.total_active_seconds}
                breakCount={daySummary.metrics.break_count}
                totalBreakSeconds={daySummary.metrics.total_break_seconds}
                firstActivity={daySummary.metrics.first_activity}
                lastActivity={daySummary.metrics.last_activity}
              />

              <CategoryBreakdown
                categorySeconds={daySummary.metrics.category_seconds}
              />

              <AISummaryCard
                aiSummary={daySummary.ai_summary}
                onRegenerate={handleRegenerate}
                loading={daySummaryLoading}
              />

              <SessionList
                sessions={daySummary.sessions}
                breaks={daySummary.breaks}
              />
            </>
          )}

          {/* Existing cards */}
          <div className="activity-grid">
            <TopAppsCard apps={summary.top_apps} />
            <TopTitlesCard titles={summary.top_titles} />
            <TopDomainsCard domains={summary.top_domains} />
          </div>
        </>
      ) : (
        <div className="activity-loading">Keine Daten fuer dieses Datum</div>
      )}
    </div>
  );
}
