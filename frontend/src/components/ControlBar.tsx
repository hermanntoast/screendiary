import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import { useStore } from "../store";
import type { TimelineEntry } from "../types";

function computeTimeLabels(
  entries: TimelineEntry[]
): { text: string; pct: number }[] {
  if (entries.length < 2) return [];
  const firstTs = new Date(entries[0]!.timestamp).getTime();
  const lastTs = new Date(entries[entries.length - 1]!.timestamp).getTime();
  const range = lastTs - firstTs;
  if (range <= 0) return [];

  const hourMs = 3600000;
  const labels: { text: string; pct: number }[] = [];

  const startHour = new Date(firstTs);
  startHour.setMinutes(0, 0, 0);
  if (startHour.getTime() <= firstTs)
    startHour.setTime(startHour.getTime() + hourMs);

  for (let t = startHour.getTime(); t <= lastTs; t += hourMs) {
    const pct = ((t - firstTs) / range) * 100;
    if (pct >= 0 && pct <= 100) {
      labels.push({
        text: new Date(t).toLocaleTimeString("de-DE", {
          hour: "2-digit",
          minute: "2-digit",
        }),
        pct,
      });
    }
  }
  return labels;
}

let lastPreloadCenter = -1;
function preloadForScrub(idx: number) {
  if (Math.abs(idx - lastPreloadCenter) < 3) return;
  lastPreloadCenter = idx;
  const { entries, monitorCount, imageCache } = useStore.getState();
  for (let i = idx - 5; i <= idx + 12; i++) {
    if (i < 0 || i >= entries.length) continue;
    const entry = entries[i]!;
    for (let m = 0; m < monitorCount; m++) {
      const key = `${entry.id}:${m}`;
      if (!imageCache.has(key)) {
        const pre = new Image();
        pre.src = `/screenshots/${entry.id}/image?monitor=${m}`;
        imageCache.set(key, pre);
      }
    }
  }
}

export function ControlBar() {
  const dates = useStore((s) => s.dates);
  const selectedDate = useStore((s) => s.selectedDate);
  const loadDate = useStore((s) => s.loadDate);
  const entries = useStore((s) => s.entries);
  const currentIndex = useStore((s) => s.currentIndex);
  const goTo = useStore((s) => s.goTo);
  const searchHitIndices = useStore((s) => s.searchHitIndices);

  const barRef = useRef<HTMLDivElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const handleRef = useRef<HTMLDivElement>(null);
  const scrubbingRef = useRef(false);
  const scrubIndexRef = useRef(-1);
  const rafRef = useRef(0);

  const entry = currentIndex >= 0 ? entries[currentIndex] : undefined;
  const timeStr = entry
    ? new Date(entry.timestamp).toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "--:--:--";
  const posStr =
    currentIndex >= 0 ? `${currentIndex + 1} / ${entries.length}` : "";

  const total = entries.length - 1;
  const pct = total > 0 ? (currentIndex / total) * 100 : 0;

  const timeLabels = useMemo(() => computeTimeLabels(entries), [entries]);

  // Imperative scrub: bypass React for performance
  const imperativeUpdate = useCallback(
    (idx: number) => {
      const state = useStore.getState();
      const { entries: e, monitorCount, imageCache } = state;
      const frame = e[idx];
      if (!frame) return;

      // Only update images if cached (prevents flicker)
      const imgs = document.querySelectorAll<HTMLImageElement>(".player-mon-img");
      for (let m = 0; m < monitorCount && m < imgs.length; m++) {
        const key = `${frame.id}:${m}`;
        const cached = imageCache.get(key);
        if (cached?.complete) {
          const img = imgs[m]!;
          if (img.src !== cached.src) img.src = cached.src;
        }
      }

      // Update text displays
      const ts = new Date(frame.timestamp);
      const timeEl = document.querySelector(".player-time-display");
      const posEl = document.querySelector(".player-pos-display");
      if (timeEl)
        timeEl.textContent = ts.toLocaleTimeString("de-DE", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
      if (posEl) posEl.textContent = `${idx + 1} / ${e.length}`;

      // Update bar position
      const p = total > 0 ? (idx / total) * 100 : 0;
      if (progressRef.current) progressRef.current.style.width = `${p}%`;
      if (handleRef.current) handleRef.current.style.left = `${p}%`;

      preloadForScrub(idx);
    },
    [total]
  );

  const scrubTo = useCallback(
    (clientX: number) => {
      const bar = barRef.current;
      if (!bar || !entries.length) return;
      const rect = bar.getBoundingClientRect();
      const p = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const idx = Math.round(p * (entries.length - 1));
      scrubIndexRef.current = idx;
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => imperativeUpdate(idx));
    },
    [entries, imperativeUpdate]
  );

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if ((e.target as HTMLElement).classList.contains("player-bar-marker"))
        return;
      scrubbingRef.current = true;

      // Clear OCR overlays during scrubbing
      document
        .querySelectorAll<HTMLCanvasElement>(".player-mon-canvas")
        .forEach((c) => {
          const ctx = c.getContext("2d");
          if (ctx) ctx.clearRect(0, 0, c.width, c.height);
        });

      scrubTo(e.clientX);
      e.preventDefault();
    },
    [scrubTo]
  );

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (scrubbingRef.current) scrubTo(e.clientX);
    }
    function onMouseUp() {
      if (scrubbingRef.current) {
        scrubbingRef.current = false;
        if (scrubIndexRef.current >= 0) {
          goTo(scrubIndexRef.current);
        }
      }
    }
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, [scrubTo, goTo]);

  // Tooltip
  const [tooltip, setTooltip] = useState<{
    visible: boolean;
    text: string;
    left: number;
  }>({ visible: false, text: "", left: 0 });

  const onBarMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!entries.length || !barRef.current) return;
      const rect = barRef.current.getBoundingClientRect();
      const p = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const idx = Math.round(p * (entries.length - 1));
      const hovered = entries[idx];
      if (!hovered) return;
      const ts = new Date(hovered.timestamp);
      setTooltip({
        visible: true,
        text: ts.toLocaleTimeString("de-DE", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
        left: e.clientX - rect.left,
      });
    },
    [entries]
  );

  const onBarMouseLeave = useCallback(() => {
    setTooltip((prev) => ({ ...prev, visible: false }));
  }, []);

  const markers = useMemo(() => {
    if (total <= 0) return [];
    const result: { idx: number; left: string; title: string }[] = [];
    searchHitIndices.forEach((idx) => {
      const e = entries[idx];
      if (e) {
        result.push({
          idx,
          left: `${(idx / total) * 100}%`,
          title: new Date(e.timestamp).toLocaleTimeString("de-DE"),
        });
      }
    });
    return result;
  }, [searchHitIndices, entries, total]);

  return (
    <div className="player-controls-overlay">
      <div className="player-info-row">
        <select
          className="player-date-select"
          value={selectedDate}
          onChange={(e) => loadDate(e.target.value)}
        >
          {dates.map((d) => (
            <option key={d.date} value={d.date}>
              {d.date} ({d.count})
            </option>
          ))}
        </select>
        <span className="player-time-display">{timeStr}</span>
        <span className="player-pos-display">{posStr}</span>
      </div>

      <div className="player-timeline">
        <div
          ref={barRef}
          className="player-bar"
          onMouseDown={onMouseDown}
          onMouseMove={onBarMouseMove}
          onMouseLeave={onBarMouseLeave}
        >
          <div
            ref={progressRef}
            className="player-bar-progress"
            style={{ width: `${pct}%` }}
          />
          <div
            ref={handleRef}
            className="player-bar-handle"
            style={{ left: `${pct}%` }}
          />
          {markers.map((m) => (
            <div
              key={m.idx}
              className="player-bar-marker"
              style={{ left: m.left }}
              title={m.title}
              onClick={(e) => {
                e.stopPropagation();
                goTo(m.idx);
              }}
            />
          ))}
          <div
            className="player-bar-tooltip"
            style={{
              display: tooltip.visible ? "block" : "none",
              left: `${tooltip.left}px`,
            }}
          >
            {tooltip.text}
          </div>
        </div>
        <div className="player-time-labels">
          {timeLabels.map((label, i) => (
            <span
              key={i}
              className="player-time-label"
              style={{ left: `${label.pct}%` }}
            >
              {label.text}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
