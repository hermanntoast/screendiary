import { useEffect, useCallback } from "react";
import { useStore } from "../store";
import { fetchOcrWords } from "../api/client";

/**
 * Draw OCR overlay on a monitor slot's canvas.
 *
 * - Canvas resolution = slot dimensions (getBoundingClientRect)
 * - Image offset computed via getBoundingClientRect for correct positioning
 * - ResizeObserver redraws on slot resize (focus/unfocus transitions)
 * - Adds/removes `has-ocr-match` class for monitor highlighting
 */
export function useOcrOverlay(
  canvasRef: React.RefObject<HTMLCanvasElement | null>,
  imgRef: React.RefObject<HTMLImageElement | null>,
  monitorIndex: number
) {
  const activeSearchQuery = useStore((s) => s.activeSearchQuery);
  const currentIndex = useStore((s) => s.currentIndex);
  const entries = useStore((s) => s.entries);

  const draw = useCallback(async () => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const slot = canvas.parentElement;
    if (!slot) return;

    const entry = entries[currentIndex];
    if (!entry || !activeSearchQuery) {
      canvas.width = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      slot.classList.remove("has-ocr-match");
      return;
    }

    try {
      const data = await fetchOcrWords(entry.id, activeSearchQuery);
      const monData = data.monitors.find(
        (m) => m.monitor_index === monitorIndex
      );

      const slotRect = slot.getBoundingClientRect();
      canvas.width = slotRect.width;
      canvas.height = slotRect.height;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (!monData) {
        slot.classList.remove("has-ocr-match");
        return;
      }

      const matched = monData.words.filter((w) => w.matched);

      if (!matched.length) {
        slot.classList.remove("has-ocr-match");
        return;
      }

      // This monitor has matches - highlight the slot
      slot.classList.add("has-ocr-match");

      // Wait for image dimensions to be available
      const nw = img.naturalWidth;
      const nh = img.naturalHeight;
      if (!nw || !nh) return;

      // Compute image position relative to slot
      const imgRect = img.getBoundingClientRect();
      const scale = Math.min(imgRect.width / nw, imgRect.height / nh);
      const offsetX = imgRect.left - slotRect.left;
      const offsetY = imgRect.top - slotRect.top;

      ctx.fillStyle = "rgba(225, 29, 72, 0.25)";
      ctx.strokeStyle = "rgba(225, 29, 72, 0.7)";
      ctx.lineWidth = 1.5;

      for (const w of matched) {
        const x = offsetX + w.left * scale;
        const y = offsetY + w.top * scale;
        const ww = w.width * scale;
        const hh = w.height * scale;
        ctx.fillRect(x, y, ww, hh);
        ctx.strokeRect(x, y, ww, hh);
      }
    } catch {
      // ignore fetch errors
    }
  }, [canvasRef, imgRef, monitorIndex, activeSearchQuery, currentIndex, entries]);

  useEffect(() => {
    draw();

    // Redraw when image loads (dimensions may not be available initially)
    const img = imgRef.current;
    const onImgLoad = () => draw();
    img?.addEventListener("load", onImgLoad);

    // Redraw on window resize
    const onResize = () => draw();
    window.addEventListener("resize", onResize);

    // Redraw when slot resizes (monitor focus/unfocus changes layout)
    const slot = canvasRef.current?.parentElement;
    let observer: ResizeObserver | null = null;
    if (slot) {
      observer = new ResizeObserver(() => {
        // Wait one frame so layout is fully settled
        requestAnimationFrame(draw);
      });
      observer.observe(slot);
    }

    return () => {
      img?.removeEventListener("load", onImgLoad);
      window.removeEventListener("resize", onResize);
      observer?.disconnect();
      slot?.classList.remove("has-ocr-match");
    };
  }, [draw, canvasRef, imgRef]);

  return draw;
}
