/**
 * Scene 4 — Link.
 *
 * White line-art, drawn as SVG on top of the canvas: concentric arcs for the
 * Earth along the bottom, a wireframe SomaiyaSat above it, and dashed beams
 * down to three ground stations. Packet dots run down the beams in priority
 * order — TT&C first, then SSTV, then M17 — which is the whole thesis of the
 * router in one picture.
 */
import { useEffect, useMemo, useRef } from "react"

import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap"
import { SCENES, sceneOpacity } from "@/hooks/useScrollScene"

const W = 1440
const H = 900

/** Sat sits up here; beams fan out to the stations on the horizon. */
const SAT = { x: 720, y: 232 }
const STATIONS = [
  { x: 330, y: 636, label: "KJSSE MUMBAI" },
  { x: 720, y: 690, label: "HELSINKI" },
  { x: 1112, y: 630, label: "SVALBARD" },
]

const PACKETS = [
  { label: "TT&C", color: "#ffffff", beam: 0, delay: 0 },
  { label: "TT&C", color: "#ffffff", beam: 1, delay: 0.18 },
  { label: "SSTV", color: "#3d6bff", beam: 2, delay: 0.75 },
  { label: "SSTV", color: "#3d6bff", beam: 0, delay: 0.95 },
  { label: "M17", color: "#8a8f98", beam: 1, delay: 1.5 },
]

export function LineArtLink({
  progressRef,
}: {
  progressRef: { current: number; visible: boolean }
}) {
  const root = useRef<SVGSVGElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const reduced = useMemo(() => prefersReducedMotion(), [])

  // Opacity is driven straight off scroll progress, outside React.
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const o = sceneOpacity(SCENES.link, progressRef.current)
      if (wrap.current) {
        wrap.current.style.opacity = String(o)
        wrap.current.style.visibility = o > 0.002 ? "visible" : "hidden"
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [progressRef])

  useGSAP(
    () => {
      if (reduced) return

      // Beams: dash offset marching downward.
      gsap.to(".beam-dash", {
        strokeDashoffset: -44,
        duration: 1.1,
        ease: "none",
        repeat: -1,
      })

      // Earth arcs breathe very slightly.
      gsap.to(".earth-arc", {
        opacity: 0.85,
        duration: 2.6,
        ease: "sine.inOut",
        repeat: -1,
        yoyo: true,
        stagger: 0.16,
      })

      // Satellite bobs.
      gsap.to(".sat-wire", {
        y: -9,
        duration: 3.2,
        ease: "sine.inOut",
        repeat: -1,
        yoyo: true,
      })

      // Packets travel down their beam in priority order, on a loop.
      PACKETS.forEach((p, i) => {
        const el = `.packet-${i}`
        const target = STATIONS[p.beam]
        gsap.set(el, { x: SAT.x, y: SAT.y, opacity: 0 })
        gsap
          .timeline({ repeat: -1, repeatDelay: 1.1, delay: p.delay })
          .to(el, { opacity: 1, duration: 0.14 })
          .to(
            el,
            {
              x: target.x,
              y: target.y,
              duration: 1.25,
              ease: "power1.in",
            },
            "<"
          )
          .to(el, { opacity: 0, duration: 0.2 }, ">-0.2")
      })

      // Station rings pulse when something lands.
      gsap.to(".station-ring", {
        scale: 1.5,
        opacity: 0,
        transformOrigin: "center",
        duration: 1.8,
        ease: "power2.out",
        repeat: -1,
        stagger: 0.45,
      })
    },
    { scope: root, dependencies: [reduced] }
  )

  return (
    <div
      ref={wrap}
      className="pointer-events-none absolute inset-0 flex items-center justify-center"
      style={{ opacity: 0, visibility: "hidden" }}
      aria-hidden="true"
    >
      <svg
        ref={root}
        viewBox={`0 0 ${W} ${H}`}
        className="h-full w-full"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        {/* ---- Earth: concentric arcs along the bottom ---- */}
        <g>
          {[0, 1, 2, 3, 4, 5].map((i) => {
            const r = 620 + i * 46
            return (
              <circle
                key={i}
                className="earth-arc"
                cx={W / 2}
                cy={1310}
                r={r}
                stroke="#ffffff"
                strokeWidth={i === 0 ? 1.4 : 1}
                opacity={0.42 - i * 0.055}
              />
            )
          })}
          {/* meridian ticks along the horizon */}
          {Array.from({ length: 22 }, (_, i) => {
            const a = Math.PI + (i / 21) * Math.PI
            const cx = W / 2
            const cy = 1310
            const r1 = 620
            const r2 = 604
            return (
              <line
                key={i}
                x1={cx + Math.cos(a) * r1}
                y1={cy + Math.sin(a) * r1}
                x2={cx + Math.cos(a) * r2}
                y2={cy + Math.sin(a) * r2}
                stroke="#ffffff"
                strokeWidth="1"
                opacity="0.22"
              />
            )
          })}
        </g>

        {/* ---- dashed beams ---- */}
        {STATIONS.map((s, i) => (
          <line
            key={i}
            className="beam-dash"
            x1={SAT.x}
            y1={SAT.y}
            x2={s.x}
            y2={s.y}
            stroke="#ffffff"
            strokeWidth="1"
            strokeDasharray="5 7"
            opacity="0.38"
          />
        ))}

        {/* ---- ground stations ---- */}
        {STATIONS.map((s, i) => (
          <g key={i}>
            <circle
              className="station-ring"
              cx={s.x}
              cy={s.y}
              r="16"
              stroke="#3d6bff"
              strokeWidth="1.2"
              opacity="0.8"
            />
            <circle cx={s.x} cy={s.y} r="4.5" fill="#3d6bff" />
            <path
              d={`M ${s.x - 15} ${s.y + 17} L ${s.x} ${s.y + 4} L ${s.x + 15} ${s.y + 17}`}
              stroke="#ffffff"
              strokeWidth="1.2"
              opacity="0.6"
            />
            <text
              x={s.x}
              y={s.y + 40}
              textAnchor="middle"
              fill="#8a8f98"
              fontSize="11"
              fontFamily="JetBrains Mono, monospace"
              letterSpacing="2"
            >
              {s.label}
            </text>
          </g>
        ))}

        {/* ---- wireframe SomaiyaSat ---- */}
        <g className="sat-wire">
          <g transform={`translate(${SAT.x} ${SAT.y})`}>
            {/* isometric cube */}
            <path
              d="M -34 -20 L 0 -40 L 34 -20 L 34 20 L 0 40 L -34 20 Z"
              stroke="#ffffff"
              strokeWidth="1.4"
              opacity="0.95"
            />
            <path
              d="M -34 -20 L 0 0 L 34 -20"
              stroke="#ffffff"
              strokeWidth="1.2"
              opacity="0.72"
            />
            <path d="M 0 0 L 0 40" stroke="#ffffff" strokeWidth="1.2" opacity="0.72" />
            {/* PCB seams */}
            <path d="M -34 -6 L 0 14 L 34 -6" stroke="#3d6bff" strokeWidth="1" opacity="0.7" />
            <path d="M -34 6 L 0 26 L 34 6" stroke="#3d6bff" strokeWidth="1" opacity="0.5" />
            {/* antenna */}
            <path d="M 0 -40 L 0 -74" stroke="#ffffff" strokeWidth="1.2" opacity="0.8" />
            <circle cx="0" cy="-78" r="3.5" fill="#3d6bff" />
            <text
              x="52"
              y="-26"
              fill="#8a8f98"
              fontSize="11"
              fontFamily="JetBrains Mono, monospace"
              letterSpacing="2"
            >
              SOMAIYASAT
            </text>
          </g>
        </g>

        {/* ---- travelling packets ---- */}
        {PACKETS.map((p, i) => (
          <g key={i} className={`packet-${i}`}>
            <circle r="5" fill={p.color} />
            <circle r="11" stroke={p.color} strokeWidth="1" opacity="0.35" />
            <text
              x="16"
              y="4"
              fill={p.color}
              fontSize="11"
              fontFamily="JetBrains Mono, monospace"
              letterSpacing="1.5"
              opacity="0.9"
            >
              {p.label}
            </text>
          </g>
        ))}

        {/* ---- caption ---- */}
        <text
          x={W / 2}
          y={806}
          textAnchor="middle"
          fill="#8a8f98"
          fontSize="12"
          fontFamily="JetBrains Mono, monospace"
          letterSpacing="3"
        >
          DOWNLINK PRIORITY · TT&amp;C → SSTV → M17 / CODEC2
        </text>
      </svg>
    </div>
  )
}
