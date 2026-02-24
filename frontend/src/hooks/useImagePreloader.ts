import { useEffect } from "react";
import { useStore } from "../store";

export function useImagePreloader() {
  const currentIndex = useStore((s) => s.currentIndex);
  const preloadAround = useStore((s) => s.preloadAround);

  useEffect(() => {
    if (currentIndex >= 0) {
      preloadAround(currentIndex);
    }
  }, [currentIndex, preloadAround]);
}
