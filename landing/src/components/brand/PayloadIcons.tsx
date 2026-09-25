/**
 * Four original white line-art icons, one per payload mode. Each is drawn on a
 * 200x200 grid so they crossfade in place without shifting.
 */

const S = { stroke: "currentColor", fill: "none", strokeLinecap: "round" as const }

/** TT&C — a dish on a mast with command ticks radiating from it. */
export function IconTTC({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} {...S}>
      {/* mast */}
      <path d="M100 196 V132" strokeWidth="2" />
      <path d="M78 196 H122" strokeWidth="2" />
      {/* dish */}
      <ellipse
        cx="100"
        cy="106"
        rx="46"
        ry="22"
        transform="rotate(-24 100 106)"
        strokeWidth="2"
      />
      <path d="M100 106 L112 78" strokeWidth="2" />
      <circle cx="113" cy="74" r="6" strokeWidth="2" />
      {/* signal ticks */}
      <path d="M128 52 A 40 40 0 0 1 150 74" strokeWidth="1.6" opacity="0.8" />
      <path d="M140 38 A 60 60 0 0 1 168 68" strokeWidth="1.6" opacity="0.55" />
      <path d="M152 24 A 80 80 0 0 1 184 62" strokeWidth="1.6" opacity="0.3" />
      {/* command pulses */}
      <circle cx="40" cy="44" r="3" fill="#3d6bff" stroke="none" />
      <circle cx="40" cy="62" r="3" fill="#3d6bff" stroke="none" />
      <circle cx="40" cy="80" r="3" fill="#3d6bff" stroke="none" />
      <path d="M50 44 H74 M50 62 H86 M50 80 H68" strokeWidth="1.6" opacity="0.7" />
    </svg>
  )
}

/** SSTV — scan lines resolving into a framed image, line by line. */
export function IconSSTV({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} {...S}>
      <rect x="28" y="36" width="144" height="112" rx="4" strokeWidth="2" />
      {/* resolved upper band */}
      {[50, 58, 66, 74, 82].map((y, i) => (
        <path
          key={y}
          d={`M38 ${y} H162`}
          strokeWidth="2.4"
          opacity={0.9 - i * 0.05}
        />
      ))}
      {/* the sweeping scan line */}
      <path d="M38 92 H162" strokeWidth="3" stroke="#3d6bff" />
      <circle cx="166" cy="92" r="4" fill="#3d6bff" stroke="none" />
      {/* not yet resolved */}
      {[102, 110, 118, 126, 134].map((y, i) => (
        <path
          key={y}
          d={`M38 ${y} H${100 + i * 12}`}
          strokeWidth="1.4"
          opacity={0.3 - i * 0.04}
        />
      ))}
      {/* base */}
      <path d="M72 148 V166 M128 148 V166 M56 166 H144" strokeWidth="2" />
    </svg>
  )
}

/** M17 — a digital waveform stepping through discrete symbol levels. */
export function IconM17({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} {...S}>
      {/* axis */}
      <path d="M20 100 H180" strokeWidth="1.2" opacity="0.35" />
      {/* 4FSK-style stepped symbols */}
      <path
        d="M24 100 V72 H44 V128 H64 V86 H84 V114 H104 V58 H124 V100 H144 V80 H164 V100 H180"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      {/* symbol boundaries */}
      {[44, 64, 84, 104, 124, 144, 164].map((x) => (
        <path key={x} d={`M${x} 46 V154`} strokeWidth="1" opacity="0.18" />
      ))}
      {/* frame markers */}
      <rect x="20" y="40" width="24" height="10" rx="2" strokeWidth="1.6" stroke="#3d6bff" />
      <rect x="156" y="150" width="24" height="10" rx="2" strokeWidth="1.6" stroke="#3d6bff" />
    </svg>
  )
}

/** Codec2 — a speech envelope squeezed down into a sparse compressed frame. */
export function IconCodec2({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" className={className} {...S}>
      {/* full-rate envelope, fading out */}
      <path
        d="M16 100 Q26 62 34 100 T52 100 T70 100 T88 100"
        strokeWidth="1.6"
        opacity="0.28"
      />
      {[20, 28, 36, 44, 52, 60, 68, 76, 84].map((x, i) => {
        const h = 10 + Math.abs(Math.sin(i * 1.3)) * 42
        return (
          <path
            key={x}
            d={`M${x} ${100 - h} V${100 + h}`}
            strokeWidth="2"
            opacity={0.5 - i * 0.035}
          />
        )
      })}
      {/* compression funnel */}
      <path d="M96 58 L116 92 L116 108 L96 142" strokeWidth="1.6" opacity="0.6" />
      <path d="M122 100 H136" strokeWidth="2" stroke="#3d6bff" />
      {/* compressed frame: few, tall bars */}
      {[144, 156, 168, 180].map((x, i) => {
        const h = 16 + ((i * 13) % 34)
        return <path key={x} d={`M${x} ${100 - h} V${100 + h}`} strokeWidth="2.6" />
      })}
      <rect x="138" y="44" width="48" height="112" rx="4" strokeWidth="1.4" opacity="0.4" />
    </svg>
  )
}

export const PAYLOAD_ICONS: Record<
  string,
  (p: { className?: string }) => React.ReactElement
> = {
  "TT&C": IconTTC,
  SSTV: IconSSTV,
  M17: IconM17,
  Codec2: IconCodec2,
}
