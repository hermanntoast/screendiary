import { useRef, useCallback } from "react";
import { useStore } from "../store";
import { useOcrOverlay } from "../hooks/useOcrOverlay";
import { TextLayer } from "./TextLayer";

interface Props {
  monitorIndex: number;
  hidden: boolean;
  focused: boolean;
}

export function MonitorSlot({ monitorIndex, hidden, focused }: Props) {
  const currentIndex = useStore((s) => s.currentIndex);
  const entries = useStore((s) => s.entries);
  const imageCache = useStore((s) => s.imageCache);
  const focusedMonitor = useStore((s) => s.focusedMonitor);
  const focusMonitor = useStore((s) => s.focusMonitor);
  const unfocusMonitor = useStore((s) => s.unfocusMonitor);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  useOcrOverlay(canvasRef, imgRef, monitorIndex);

  const entry = currentIndex >= 0 ? entries[currentIndex] : undefined;
  let imgSrc = "";
  if (entry) {
    const key = `${entry.id}:${monitorIndex}`;
    const cached = imageCache.get(key);
    if (cached?.complete) {
      imgSrc = cached.src;
    } else {
      imgSrc = `/screenshots/${entry.id}/image?monitor=${monitorIndex}`;
    }
  }

  const onClick = useCallback(() => {
    if (focusedMonitor !== monitorIndex) {
      focusMonitor(monitorIndex);
    }
  }, [focusedMonitor, monitorIndex, focusMonitor]);

  const onClose = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      unfocusMonitor();
    },
    [unfocusMonitor]
  );

  const className = [
    "player-mon-slot",
    hidden ? "hidden" : "",
    focused ? "focused" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={className} onClick={onClick}>
      {imgSrc && (
        <img
          ref={imgRef}
          className="player-mon-img"
          src={imgSrc}
          alt={`Monitor ${monitorIndex}`}
          draggable={false}
        />
      )}
      <canvas ref={canvasRef} className="player-mon-canvas" />
      {focused && <TextLayer monitorIndex={monitorIndex} imgRef={imgRef} />}
      {focused && (
        <button className="player-mon-close" onClick={onClose} title="Schließen (Esc)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 6 6 18" />
            <path d="m6 6 12 12" />
          </svg>
        </button>
      )}
    </div>
  );
}
