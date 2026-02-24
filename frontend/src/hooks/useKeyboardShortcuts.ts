import { useEffect } from "react";
import { useStore } from "../store";

export function useKeyboardShortcuts(searchInputRef: React.RefObject<HTMLInputElement | null>) {
  const goTo = useStore((s) => s.goTo);
  const currentIndex = useStore((s) => s.currentIndex);
  const entriesLength = useStore((s) => s.entries.length);
  const focusedMonitor = useStore((s) => s.focusedMonitor);
  const unfocusMonitor = useStore((s) => s.unfocusMonitor);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept when typing in the search input
      if (e.target === searchInputRef.current) {
        if (e.key === "Escape") {
          searchInputRef.current?.blur();
          e.preventDefault();
        }
        return;
      }

      switch (e.key) {
        case "ArrowLeft":
          e.preventDefault();
          goTo(currentIndex - 1);
          break;
        case "ArrowRight":
          e.preventDefault();
          goTo(currentIndex + 1);
          break;
        case "Home":
          e.preventDefault();
          goTo(0);
          break;
        case "End":
          e.preventDefault();
          goTo(entriesLength - 1);
          break;
        case "Escape":
          if (focusedMonitor >= 0) {
            unfocusMonitor();
            e.preventDefault();
          }
          break;
        case "s":
        case "f":
          if (!e.ctrlKey && !e.metaKey) {
            searchInputRef.current?.focus();
            e.preventDefault();
          }
          break;
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [goTo, currentIndex, entriesLength, focusedMonitor, unfocusMonitor, searchInputRef]);
}
