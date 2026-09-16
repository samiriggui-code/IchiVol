const CANDLES = [
  { bull: true, top: 118, bottom: 104, wickTop: 122, wickBottom: 98 },
  { bull: false, top: 108, bottom: 116, wickTop: 104, wickBottom: 120 },
  { bull: true, top: 102, bottom: 112, wickTop: 116, wickBottom: 96 },
  { bull: true, top: 92, bottom: 104, wickTop: 108, wickBottom: 86 },
  { bull: false, top: 90, bottom: 98, wickTop: 84, wickBottom: 102 },
  { bull: true, top: 78, bottom: 92, wickTop: 96, wickBottom: 72 },
  { bull: true, top: 68, bottom: 80, wickTop: 84, wickBottom: 62 },
  { bull: true, top: 58, bottom: 70, wickTop: 74, wickBottom: 52 },
  { bull: false, top: 56, bottom: 64, wickTop: 50, wickBottom: 68 },
  { bull: true, top: 44, bottom: 58, wickTop: 62, wickBottom: 38 },
  { bull: true, top: 34, bottom: 46, wickTop: 50, wickBottom: 28 },
  { bull: true, top: 26, bottom: 38, wickTop: 42, wickBottom: 20 },
]

export function IchimokuMockChart() {
  const step = 320 / (CANDLES.length + 1)
  return (
    <svg
      viewBox="0 0 320 150"
      className="camap-mock-chart"
      role="img"
      aria-label="Aperçu schématique d’un nuage Ichimoku en cassure haussière"
    >
      <defs>
        <linearGradient id="ichiMockCloudFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.32" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0.05" />
        </linearGradient>
      </defs>
      <path
        d="M0,100 C50,94 70,78 110,80 C150,82 170,66 210,62 C250,58 290,48 320,44 L320,86 C290,92 250,102 210,104 C170,106 150,118 110,116 C70,114 50,106 0,110 Z"
        fill="url(#ichiMockCloudFill)"
      />
      <path
        d="M0,100 C50,94 70,78 110,80 C150,82 170,66 210,62 C250,58 290,48 320,44"
        fill="none"
        stroke="var(--primary)"
        strokeOpacity="0.6"
        strokeWidth="1.4"
      />
      <path
        d="M0,110 C50,106 70,114 110,116 C150,118 170,106 210,104 C250,102 290,92 320,86"
        fill="none"
        stroke="var(--primary)"
        strokeOpacity="0.32"
        strokeWidth="1.4"
      />
      {CANDLES.map((c, i) => {
        const x = step * (i + 1)
        const color = c.bull ? 'var(--primary)' : 'var(--destructive)'
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={c.wickTop} y2={c.wickBottom} stroke={color} strokeOpacity="0.6" strokeWidth="1" />
            <rect
              x={x - 4}
              y={Math.min(c.top, c.bottom)}
              width="8"
              height={Math.max(2, Math.abs(c.bottom - c.top))}
              fill={color}
              fillOpacity="0.85"
              rx="1.5"
            />
          </g>
        )
      })}
    </svg>
  )
}
