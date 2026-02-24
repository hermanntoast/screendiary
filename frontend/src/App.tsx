import { useEffect, useRef, useState, useCallback } from "react";
import { useStore } from "./store";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { useImagePreloader } from "./hooks/useImagePreloader";
import { TopBar } from "./components/TopBar";
import { Viewport } from "./components/Viewport";
import { ControlBar } from "./components/ControlBar";
import { NavBar } from "./components/NavBar";
import { ActivityPage } from "./components/activity/ActivityPage";
import { StoragePage } from "./components/storage/StoragePage";
import { ChatPage } from "./components/chat/ChatPage";

function getPage(): string {
  const hash = window.location.hash.replace("#", "") || "chat";
  if (hash === "player") return "player";
  if (hash === "activity") return "activity";
  if (hash === "storage") return "storage";
  return "chat";
}

function PlayerView() {
  const loadDates = useStore((s) => s.loadDates);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDates();
  }, [loadDates]);

  useKeyboardShortcuts(searchInputRef);
  useImagePreloader();

  return (
    <div className="player">
      <Viewport />
      <TopBar searchInputRef={searchInputRef} />
      <ControlBar />
    </div>
  );
}

export function App() {
  const [page, setPage] = useState(getPage);

  useEffect(() => {
    const onHash = () => setPage(getPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = useCallback((target: string) => {
    window.location.hash = target;
  }, []);

  return (
    <>
      <NavBar currentPage={page} onNavigate={navigate} />
      <div className="app-content">
        {page === "chat" ? <ChatPage /> : page === "storage" ? <StoragePage /> : page === "activity" ? <ActivityPage /> : <PlayerView />}
      </div>
    </>
  );
}
