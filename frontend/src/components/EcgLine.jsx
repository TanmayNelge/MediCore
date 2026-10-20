// Decorative animated heartbeat line used as background art.
export default function EcgLine({ className = "", stroke = "#3fd0b4", animated = true, opacity = 1 }) {
  return (
    <svg
      className={className}
      viewBox="0 0 800 140"
      preserveAspectRatio="none"
      fill="none"
      aria-hidden="true"
      style={{ opacity }}
    >
      <defs>
        <linearGradient id="ecgFade" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stopColor={stroke} stopOpacity="0" />
          <stop offset="0.35" stopColor={stroke} stopOpacity="1" />
          <stop offset="0.8" stopColor={stroke} stopOpacity="1" />
          <stop offset="1" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 76 H170 l14 -9 l14 9 H262 l12 14 l20 -84 l24 118 l16 -48 H420 l16 -16 l18 16 H560 l12 10 l18 -62 l20 86 l12 -34 H800"
        stroke="url(#ecgFade)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={animated ? "ecg-line animate-ecg" : ""}
        style={animated ? undefined : { strokeDasharray: "none" }}
      />
    </svg>
  );
}
