/**
 * Deterministic HSL color from a string hash.
 * Same app_class always produces the same color.
 */
export function appColor(appClass: string): string {
  let hash = 0;
  for (let i = 0; i < appClass.length; i++) {
    hash = appClass.charCodeAt(i) + ((hash << 5) - hash);
    hash |= 0;
  }
  const hue = ((hash % 360) + 360) % 360;
  return `hsl(${hue}, 65%, 55%)`;
}

/**
 * Format seconds into human-readable duration.
 * Examples: "2h 15m", "45m", "30s"
 */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) {
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  return `${m}m`;
}
