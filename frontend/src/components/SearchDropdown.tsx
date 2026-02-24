import { useEffect, useRef } from "react";
import { useStore } from "../store";

export function SearchDropdown() {
  const searchResults = useStore((s) => s.searchResults);
  const jumpToScreenshot = useStore((s) => s.jumpToScreenshot);
  const setShowSearchDropdown = useStore((s) => s.setShowSearchDropdown);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const dropdown = dropdownRef.current;
      if (!dropdown) return;
      const target = e.target as HTMLElement;
      // Don't close if clicking inside dropdown or on the search input
      if (
        dropdown.contains(target) ||
        target.closest(".player-search-box")
      )
        return;
      setShowSearchDropdown(false);
    }
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, [setShowSearchDropdown]);

  if (!searchResults.length) {
    return (
      <div className="player-search-results" style={{ display: "block" }} ref={dropdownRef}>
        <div className="psr-empty">Keine Treffer</div>
      </div>
    );
  }

  return (
    <div className="player-search-results" style={{ display: "block" }} ref={dropdownRef}>
      {searchResults.slice(0, 20).map((r) => (
        <div
          key={r.screenshot_id}
          className="psr-item"
          onClick={(e) => {
            e.stopPropagation();
            jumpToScreenshot(r.screenshot_id, r.date);
            setShowSearchDropdown(false);
          }}
        >
          <span className="psr-time">
            {new Date(r.timestamp).toLocaleString("de-DE")}
          </span>
          {r.highlights?.map((h, i) => (
            <span
              key={i}
              className="psr-hl"
              dangerouslySetInnerHTML={{ __html: h }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
