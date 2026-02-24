import { useStore } from "../store";
import { MonitorSlot } from "./MonitorSlot";

export function Viewport() {
  const entries = useStore((s) => s.entries);
  const currentIndex = useStore((s) => s.currentIndex);
  const monitorCount = useStore((s) => s.monitorCount);
  const focusedMonitor = useStore((s) => s.focusedMonitor);

  if (currentIndex < 0) {
    return (
      <div className="player-monitors">
        <div className="player-placeholder">
          {entries.length === 0 ? "Lade..." : "Keine Screenshots"}
        </div>
      </div>
    );
  }

  return (
    <div className="player-monitors">
      {Array.from({ length: monitorCount }, (_, i) => (
        <MonitorSlot
          key={i}
          monitorIndex={i}
          hidden={focusedMonitor >= 0 && focusedMonitor !== i}
          focused={focusedMonitor === i}
        />
      ))}
    </div>
  );
}
