import { useRef, useCallback } from "react";
import { useStore } from "../store";
import { SearchDropdown } from "./SearchDropdown";

interface Props {
  searchInputRef: React.RefObject<HTMLInputElement | null>;
}

export function TopBar({ searchInputRef }: Props) {
  const searchQuery = useStore((s) => s.searchQuery);
  const setSearchQuery = useStore((s) => s.setSearchQuery);
  const executeSearch = useStore((s) => s.executeSearch);
  const clearSearch = useStore((s) => s.clearSearch);
  const showSearchDropdown = useStore((s) => s.showSearchDropdown);
  const setShowSearchDropdown = useStore((s) => s.setShowSearchDropdown);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null);

  const onSearchInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const q = e.target.value;
      setSearchQuery(q);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      const trimmed = q.trim();
      if (!trimmed) {
        clearSearch();
        return;
      }
      debounceRef.current = setTimeout(() => executeSearch(trimmed), 300);
    },
    [setSearchQuery, executeSearch, clearSearch]
  );

  const onSearchKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const q = searchQuery.trim();
        if (q) executeSearch(q);
      }
      if (e.key === "Escape") {
        clearSearch();
        searchInputRef.current?.blur();
      }
    },
    [searchQuery, executeSearch, clearSearch, searchInputRef]
  );

  const onSearchFocus = useCallback(() => {
    if (useStore.getState().searchResults.length > 0) {
      setShowSearchDropdown(true);
    }
  }, [setShowSearchDropdown]);

  return (
    <div className="player-search-overlay">
      <div className="player-search-box">
        <input
          ref={searchInputRef}
          type="text"
          placeholder="Text suchen... (S)"
          autoComplete="off"
          value={searchQuery}
          onChange={onSearchInput}
          onKeyDown={onSearchKeyDown}
          onFocus={onSearchFocus}
        />
        {showSearchDropdown && <SearchDropdown />}
      </div>
    </div>
  );
}
