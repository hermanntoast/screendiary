import { useEffect, useState, useRef, useCallback } from "react";
import { useStore } from "../store";
import { fetchAllOcrWords } from "../api/client";
import type { OcrWord } from "../types";

interface Props {
  monitorIndex: number;
  imgRef: React.RefObject<HTMLImageElement | null>;
}

interface TextLine {
  top: number;
  left: number;
  height: number;
  fontSize: number;
  text: string;
}

/**
 * Group OCR words into lines by Y-proximity, sort each line by X,
 * then join words into a single string per line.
 */
function buildLines(
  words: OcrWord[],
  scale: number,
  offsetX: number,
  offsetY: number
): TextLine[] {
  if (!words.length) return [];

  const sorted = [...words].sort((a, b) => a.top - b.top || a.left - b.left);
  const avgHeight = words.reduce((s, w) => s + w.height, 0) / words.length;
  const threshold = avgHeight * 0.5;

  const groups: OcrWord[][] = [];
  let cur: OcrWord[] = [sorted[0]!];
  let curTop = sorted[0]!.top;

  for (let i = 1; i < sorted.length; i++) {
    const w = sorted[i]!;
    if (Math.abs(w.top - curTop) <= threshold) {
      cur.push(w);
    } else {
      groups.push(cur.sort((a, b) => a.left - b.left));
      cur = [w];
      curTop = w.top;
    }
  }
  groups.push(cur.sort((a, b) => a.left - b.left));

  return groups.map((lineWords) => {
    const minTop = Math.min(...lineWords.map((w) => w.top));
    const maxBot = Math.max(...lineWords.map((w) => w.top + w.height));
    const h = maxBot - minTop;
    const firstWord = lineWords[0]!;

    return {
      top: offsetY + minTop * scale,
      left: offsetX + firstWord.left * scale,
      height: h * scale,
      fontSize: Math.max(6, h * scale * 0.82),
      text: lineWords.map((w) => w.word).join(" "),
    };
  });
}

export function TextLayer({ monitorIndex, imgRef }: Props) {
  const currentIndex = useStore((s) => s.currentIndex);
  const entries = useStore((s) => s.entries);
  const layerRef = useRef<HTMLDivElement>(null);
  const [words, setWords] = useState<OcrWord[]>([]);
  const [lines, setLines] = useState<TextLine[]>([]);

  const entry = currentIndex >= 0 ? entries[currentIndex] : undefined;

  useEffect(() => {
    if (!entry) {
      setWords([]);
      return;
    }
    let cancelled = false;
    fetchAllOcrWords(entry.id)
      .then((data) => {
        if (cancelled) return;
        const monData = data.monitors.find(
          (m) => m.monitor_index === monitorIndex
        );
        setWords(monData?.words ?? []);
      })
      .catch(() => {
        if (!cancelled) setWords([]);
      });
    return () => {
      cancelled = true;
    };
  }, [entry, monitorIndex]);

  const reposition = useCallback(() => {
    const layer = layerRef.current;
    const img = imgRef.current;
    if (!layer || !img || !words.length) {
      setLines([]);
      return;
    }

    const slot = layer.parentElement;
    if (!slot) return;

    const nw = img.naturalWidth;
    const nh = img.naturalHeight;
    if (!nw || !nh) return;

    const slotRect = slot.getBoundingClientRect();
    const imgRect = img.getBoundingClientRect();
    const scale = Math.min(imgRect.width / nw, imgRect.height / nh);
    const offsetX = imgRect.left - slotRect.left;
    const offsetY = imgRect.top - slotRect.top;

    setLines(buildLines(words, scale, offsetX, offsetY));
  }, [words, imgRef]);

  useEffect(() => {
    const timer = setTimeout(reposition, 250);

    const img = imgRef.current;
    const onLoad = () => reposition();
    img?.addEventListener("load", onLoad);

    window.addEventListener("resize", reposition);

    const slot = layerRef.current?.parentElement;
    let observer: ResizeObserver | null = null;
    if (slot) {
      observer = new ResizeObserver(() => requestAnimationFrame(reposition));
      observer.observe(slot);
    }

    return () => {
      clearTimeout(timer);
      img?.removeEventListener("load", onLoad);
      window.removeEventListener("resize", reposition);
      observer?.disconnect();
    };
  }, [reposition, imgRef]);

  return (
    <div
      ref={layerRef}
      className="player-text-layer"
      onMouseDown={(e) => e.stopPropagation()}
    >
      {lines.map((line, i) => (
        <div
          key={i}
          className="player-text-line"
          style={{
            top: `${line.top}px`,
            left: `${line.left}px`,
            height: `${line.height}px`,
            fontSize: `${line.fontSize}px`,
            lineHeight: `${line.height}px`,
          }}
        >
          {line.text}
        </div>
      ))}
    </div>
  );
}
