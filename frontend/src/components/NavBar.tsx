interface Props {
  currentPage: string;
  onNavigate: (page: string) => void;
}

export function NavBar({ currentPage, onNavigate }: Props) {
  return (
    <nav className="navbar">
      <span className="navbar-brand">
        <img src="/favicon.png" alt="SD" className="navbar-icon" />
        ScreenDiary
      </span>
      <div className="navbar-links">
        <button
          className={`navbar-link ${currentPage === "player" ? "navbar-link-active" : ""}`}
          onClick={() => onNavigate("player")}
        >
          Player
        </button>
        <button
          className={`navbar-link ${currentPage === "activity" ? "navbar-link-active" : ""}`}
          onClick={() => onNavigate("activity")}
        >
          Aktivitaeten
        </button>
        <button
          className={`navbar-link ${currentPage === "storage" ? "navbar-link-active" : ""}`}
          onClick={() => onNavigate("storage")}
        >
          Speicher
        </button>
      </div>
    </nav>
  );
}
