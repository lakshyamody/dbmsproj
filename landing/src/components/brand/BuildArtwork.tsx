/**
 * Original artwork for [ THE BUILD ].
 *
 * The KJS-SRS-01 PDF is not committed to this repo, so rather than reproduce
 * its figures these are drawn from scratch: an exploded view of the deployer
 * and its spacecraft, a dimensioned drawing built from the numbers in Fig. 2,
 * and a schematic of the ground software. All plain SVG, crisp at any size.
 *
 * Drop the PDF into landing/public/assets/source/KJS-SRS-01.pdf and
 * scripts/prepare_assets.py will extract the real Fig. 1 photograph instead.
 */

const LINE = { fill: "none", stroke: "currentColor", strokeLinecap: "round" as const }

/** Card 1 — the deployer with the PocketQube part-way out of the rails. */
export function ArtFlightHardware({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 400" className={className} {...LINE}>
      <defs>
        <pattern id="solar" width="8" height="8" patternUnits="userSpaceOnUse">
          <path d="M0 8 L8 0" stroke="currentColor" strokeWidth="0.6" opacity="0.5" />
        </pattern>
      </defs>

      {/* deployer body, isometric */}
      <path d="M92 250 L92 132 L214 78 L214 196 Z" strokeWidth="1.6" />
      <path d="M92 250 L262 316 L262 198 L92 132" strokeWidth="1.6" />
      <path d="M214 78 L384 144 L262 198" strokeWidth="1.6" />
      <path d="M262 316 L384 262 L384 144" strokeWidth="1.6" opacity="0.55" />

      {/* internal rails */}
      <path d="M120 156 L282 222" strokeWidth="0.9" opacity="0.45" />
      <path d="M120 226 L282 292" strokeWidth="0.9" opacity="0.45" />
      <path d="M186 104 L348 170" strokeWidth="0.9" opacity="0.45" />

      {/* hinged door, swung open */}
      <g opacity="0.9">
        <path d="M384 144 L470 84 L470 200 L384 262" strokeWidth="1.5" />
        <path d="M398 152 L456 110 L456 186 L398 232" strokeWidth="0.8" opacity="0.5" />
        <path d="M384 144 L384 262" strokeWidth="2" stroke="#3d6bff" />
      </g>

      {/* the spacecraft, sliding clear — elongated to the real 127 x 58 x 57
          envelope rather than the cube "PocketQube" implies */}
      <g>
        {/* long front face */}
        <path d="M468 196 L568 235 L568 189 L468 150 Z" strokeWidth="1.6" />
        {/* end face */}
        <path d="M568 235 L612 216 L612 170 L568 189 Z" strokeWidth="1.6" />
        {/* top */}
        <path d="M468 150 L568 189 L612 170 L512 131 Z" strokeWidth="1.6" />
        {/* solar cells along the long face */}
        <path d="M486 181 L556 208 L556 184 L486 157 Z" fill="url(#solar)" stroke="none" />
        {/* PCB deck seams */}
        <path
          d="M468 181 L568 220 M468 166 L568 205"
          strokeWidth="1"
          stroke="#3d6bff"
          opacity="0.85"
        />
        {/* antenna off the top face */}
        <path d="M540 160 L540 116" strokeWidth="1.2" />
        <circle cx="540" cy="112" r="4" fill="#3d6bff" stroke="none" />
      </g>

      {/* motion cue */}
      <path d="M400 214 L452 234" strokeWidth="1" strokeDasharray="4 6" opacity="0.5" />
      <path d="M440 226 L452 234 L438 240" strokeWidth="1" opacity="0.5" />

      {/* callouts */}
      <g opacity="0.7" fontFamily="JetBrains Mono, monospace" fontSize="10" letterSpacing="1.5">
        <path d="M150 300 L150 330 L250 330" strokeWidth="0.8" />
        <text x="258" y="334" fill="currentColor" stroke="none">SOMAIYAPOD DEPLOYER</text>
        <path d="M596 150 L612 150 L612 104" strokeWidth="0.8" />
        <text x="612" y="96" textAnchor="end" fill="currentColor" stroke="none">SOMAIYASAT</text>
      </g>
    </svg>
  )
}

/**
 * Card 2 — dimensioned drawing of SomaiyaSat's actual envelope.
 *
 * Per Fig. 2 of KJS-SRS-01 this is 127.4 x 57.9 x 57.2 mm — an elongated PCB
 * stack, not the 50 mm cube that "PocketQube" suggests. (50 mm is the generic
 * 1P unit the document's background section describes; this spacecraft is
 * roughly 2.5P long.)
 */
export function ArtFormFactor({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 400" className={className} {...LINE}>
      {/* ---- side elevation: the long axis ---- */}
      <rect x="96" y="150" width="382" height="112" strokeWidth="1.8" />

      {/* PCB decks through the stack */}
      {[96, 172, 248, 324, 400].map((x) => (
        <path key={x} d={`M${x} 150 V262`} strokeWidth="0.9" opacity="0.45" />
      ))}
      {/* solar cells along the long face */}
      {[110, 186, 262, 338, 414].map((x) => (
        <rect
          key={x}
          x={x}
          y="158"
          width="52"
          height="22"
          strokeWidth="0.8"
          opacity="0.75"
        />
      ))}
      {/* standoff rails top and bottom */}
      <path d="M96 156 H478 M96 256 H478" strokeWidth="0.8" opacity="0.5" />

      {/* antenna */}
      <path d="M287 150 V96" strokeWidth="1.4" />
      <circle cx="287" cy="92" r="5" fill="#3d6bff" stroke="none" />

      {/* ---- length dimension ---- */}
      <g stroke="#3d6bff">
        <path d="M96 300 H478" strokeWidth="1" />
        <path d="M96 292 V308 M478 292 V308" strokeWidth="1" />
        <path d="M106 294 L96 300 L106 306 M468 294 L478 300 L468 306" strokeWidth="1" />
      </g>
      <text
        x="287"
        y="326"
        textAnchor="middle"
        fill="#3d6bff"
        stroke="none"
        fontFamily="JetBrains Mono, monospace"
        fontSize="13"
        letterSpacing="2"
      >
        127.4 mm
      </text>

      {/* ---- height dimension ---- */}
      <g stroke="#3d6bff">
        <path d="M512 150 V262" strokeWidth="1" />
        <path d="M504 150 H520 M504 262 H520" strokeWidth="1" />
        <path d="M506 160 L512 150 L518 160 M506 252 L512 262 L518 252" strokeWidth="1" />
      </g>
      <text
        x="530"
        y="212"
        fill="#3d6bff"
        stroke="none"
        fontFamily="JetBrains Mono, monospace"
        fontSize="13"
        letterSpacing="2"
      >
        57.2 mm
      </text>

      {/* ---- end elevation, ghosted ---- */}
      <g opacity="0.42">
        <rect x="96" y="40" width="114" height="112" strokeWidth="1.2" fill="none" />
        <path d="M96 96 H210 M153 40 V152" strokeWidth="0.7" />
        <text
          x="153"
          y="32"
          textAnchor="middle"
          fill="currentColor"
          stroke="none"
          fontFamily="JetBrains Mono, monospace"
          fontSize="10"
          letterSpacing="1.5"
        >
          END · 57.9 WIDE
        </text>
      </g>

      {/* centre line */}
      <path d="M76 206 H498" strokeWidth="0.6" strokeDasharray="8 4 2 4" opacity="0.3" />

      <text
        x="96"
        y="372"
        fill="currentColor"
        stroke="none"
        opacity="0.6"
        fontFamily="JetBrains Mono, monospace"
        fontSize="10"
        letterSpacing="1.5"
      >
        POCKETQUBE STACK · 1.6 MM PCB · SIDE ELEVATION
      </text>
    </svg>
  )
}

/** Card 3 — schematic of the ground-control screen, used until a real capture exists. */
export function ArtGroundSoftware({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 400" className={className} {...LINE}>
      {/* window chrome */}
      <rect x="40" y="40" width="560" height="320" rx="8" strokeWidth="1.4" />
      <path d="M40 78 H600" strokeWidth="1" opacity="0.6" />
      <circle cx="62" cy="59" r="4" strokeWidth="1" opacity="0.6" />
      <circle cx="78" cy="59" r="4" strokeWidth="1" opacity="0.6" />
      <circle cx="94" cy="59" r="4" strokeWidth="1" opacity="0.6" />

      {/* globe */}
      <circle cx="250" cy="220" r="86" strokeWidth="1.2" opacity="0.85" />
      <ellipse cx="250" cy="220" rx="86" ry="30" strokeWidth="0.8" opacity="0.4" />
      <ellipse cx="250" cy="220" rx="34" ry="86" strokeWidth="0.8" opacity="0.4" />
      <path d="M164 220 H336" strokeWidth="0.8" opacity="0.4" />
      {/* orbit + sat */}
      <ellipse
        cx="250"
        cy="220"
        rx="116"
        ry="44"
        transform="rotate(-24 250 220)"
        strokeWidth="1"
        stroke="#3d6bff"
        opacity="0.8"
      />
      <circle cx="352" cy="180" r="5" fill="#3d6bff" stroke="none" />
      {/* station pings */}
      <circle cx="286" cy="196" r="3.5" fill="currentColor" stroke="none" opacity="0.9" />
      <circle cx="286" cy="196" r="11" strokeWidth="0.9" opacity="0.45" />
      <circle cx="212" cy="178" r="3" fill="currentColor" stroke="none" opacity="0.7" />

      {/* left panel */}
      <rect x="60" y="96" width="120" height="120" rx="6" strokeWidth="1" opacity="0.55" />
      <path d="M72 120 H150 M72 136 H132 M72 152 H158 M72 168 H120" strokeWidth="1.6" opacity="0.4" />
      {/* payload chips */}
      {[0, 1, 2, 3].map((i) => (
        <circle key={i} cx={78 + i * 26} cy={194} r="9" strokeWidth="1" opacity={i === 1 ? 0.25 : 0.8} />
      ))}

      {/* right cards */}
      {[96, 178, 260].map((y, i) => (
        <g key={y}>
          <rect x="424" y={y} width="156" height="68" rx="6" strokeWidth="1" opacity="0.55" />
          <path d={`M440 ${y + 24} H520`} strokeWidth="1.6" opacity="0.4" />
          <path
            d={`M440 ${y + 44} H${482 + i * 14}`}
            strokeWidth="3"
            stroke="#3d6bff"
            opacity="0.75"
          />
        </g>
      ))}

      {/* sparkline */}
      <path
        d="M60 320 L86 306 L112 314 L138 296 L164 302 L190 286 L216 292 L242 276"
        strokeWidth="1.6"
        stroke="#3d6bff"
      />
    </svg>
  )
}
