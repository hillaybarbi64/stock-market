/*
  Small line-icons for the sidebar. Stroke inherits currentColor so the active
  state (green) and rest state (faint) come from the parent link.
*/

export type IconName =
  | "grid"
  | "layers"
  | "swap"
  | "book"
  | "chart"
  | "shield"
  | "bulb"
  | "file"
  | "doc"
  | "refresh"
  | "link"
  | "sliders"
  | "news"
  | "pulse";

const PATHS: Record<IconName, React.ReactNode> = {
  grid: (
    <>
      <rect x="2.5" y="2.5" width="4.6" height="4.6" rx="1" />
      <rect x="8.9" y="2.5" width="4.6" height="4.6" rx="1" />
      <rect x="2.5" y="8.9" width="4.6" height="4.6" rx="1" />
      <rect x="8.9" y="8.9" width="4.6" height="4.6" rx="1" />
    </>
  ),
  layers: (
    <>
      <path d="M8 2.4l5.6 2.8L8 8 2.4 5.2 8 2.4z" />
      <path d="M2.4 8.2 8 11l5.6-2.8" />
      <path d="M2.4 10.7 8 13.5l5.6-2.8" />
    </>
  ),
  swap: (
    <>
      <path d="M5 13V4M5 4 2.7 6.3M5 4l2.3 2.3" />
      <path d="M11 3v9M11 12l2.3-2.3M11 12l-2.3-2.3" />
    </>
  ),
  book: (
    <>
      <rect x="3.5" y="2.5" width="9" height="11" rx="1" />
      <line x1="6" y1="2.5" x2="6" y2="13.5" />
    </>
  ),
  chart: (
    <>
      <polyline points="2.5,11 6,7.5 8.5,9.5 13.5,4" />
      <path d="M2.5 13.5h11" />
    </>
  ),
  shield: (
    <>
      <path d="M8 2.4l4.6 1.8v3.4c0 3-2 5-4.6 5.9-2.6-.9-4.6-2.9-4.6-5.9V4.2z" />
      <line x1="8" y1="6" x2="8" y2="9" />
    </>
  ),
  bulb: (
    <>
      <path d="M8 2.4a4 4 0 0 1 2.5 7.1c-.5.4-.8 1-.8 1.6H6.3c0-.6-.3-1.2-.8-1.6A4 4 0 0 1 8 2.4z" />
      <line x1="6.5" y1="13" x2="9.5" y2="13" />
    </>
  ),
  file: (
    <>
      <path d="M4 2.5h5l3.4 3.4v8H4z" />
      <path d="M9 2.5v3.4h3.4" />
      <line x1="6" y1="9" x2="10.5" y2="9" />
      <line x1="6" y1="11" x2="9" y2="11" />
    </>
  ),
  doc: (
    <>
      <rect x="2.5" y="3.5" width="11" height="9" rx="1" />
      <line x1="4.6" y1="6.2" x2="8" y2="6.2" />
      <line x1="4.6" y1="8.5" x2="11.4" y2="8.5" />
      <line x1="4.6" y1="10.5" x2="11.4" y2="10.5" />
    </>
  ),
  refresh: (
    <>
      <path d="M12.6 6A5 5 0 0 0 4 4.4M3.4 3v3h3" />
      <path d="M3.4 10A5 5 0 0 0 12 11.6M12.6 13v-3h-3" />
    </>
  ),
  link: (
    <>
      <path d="M6.7 9.3 9.3 6.7" />
      <path d="M5.1 11.8 3.9 13a2.1 2.1 0 0 1-3-3l2.7-2.7a2.1 2.1 0 0 1 3 0" />
      <path d="m10.9 4.2 1.2-1.2a2.1 2.1 0 0 1 3 3l-2.7 2.7a2.1 2.1 0 0 1-3 0" />
    </>
  ),
  sliders: (
    <>
      <line x1="3" y1="5" x2="13" y2="5" />
      <circle cx="6" cy="5" r="1.7" />
      <line x1="3" y1="11" x2="13" y2="11" />
      <circle cx="10" cy="11" r="1.7" />
    </>
  ),
  pulse: <path d="M2.5 8h2.5l1.5-4 2.5 8 1.5-4h3" />,
  news: (
    <>
      <path d="M2.5 4h8v9H3.6A1.1 1.1 0 0 1 2.5 11.9z" />
      <path d="M10.5 6.5h2.4a.6.6 0 0 1 .6.6V12a1 1 0 0 1-1 1" />
      <line x1="4.3" y1="6.2" x2="8.7" y2="6.2" />
      <line x1="4.3" y1="8.4" x2="8.7" y2="8.4" />
      <line x1="4.3" y1="10.6" x2="7" y2="10.6" />
    </>
  ),
};

export function NavIcon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={`size-4 shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {PATHS[name]}
    </svg>
  );
}
