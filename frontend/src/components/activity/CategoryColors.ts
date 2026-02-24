/** Shared category color mapping used across all activity components. */

export const CATEGORY_COLORS: Record<string, string> = {
  coding: "#3b82f6",       // blue
  terminal: "#14b8a6",     // teal
  browser: "#f97316",      // orange
  communication: "#a855f7", // purple
  media: "#ec4899",        // pink
  files: "#22c55e",        // green
  office: "#eab308",       // yellow
  other: "#71717a",        // gray
};

export const CATEGORY_LABELS: Record<string, string> = {
  coding: "Coding",
  terminal: "Terminal",
  browser: "Browser",
  communication: "Kommunikation",
  media: "Medien",
  files: "Dateien",
  office: "Office",
  other: "Sonstiges",
};

export function categoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? CATEGORY_COLORS.other!;
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? CATEGORY_LABELS.other!;
}
