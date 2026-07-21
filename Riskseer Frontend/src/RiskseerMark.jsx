import "./RiskseerMark.css";

export default function RiskseerMark({ className = "", labelled = false }) {
  const classes = ["riskseer-mark", className].filter(Boolean).join(" ");

  return (
    <svg
      className={classes}
      viewBox="0 0 72 48"
      role={labelled ? "img" : undefined}
      aria-hidden={labelled ? undefined : "true"}
      aria-label={labelled ? "Riskseer eye logo" : undefined}
    >
      <path className="riskseer-mark__eye" d="M4 24C13 10 24 4 36 4s23 6 32 20c-9 14-20 20-32 20S13 38 4 24Z" />
      <circle className="riskseer-mark__iris" cx="36" cy="24" r="10" />
      <circle className="riskseer-mark__pupil" cx="36" cy="24" r="7" />
      <text className="riskseer-mark__letter" x="36" y="24">R</text>
    </svg>
  );
}
