/**
 * [ HOW IT DECIDES ] — the router architecture as an animated SVG.
 *
 * Four sensing inputs feed the Autonomous Manager, which selects among the
 * payload modes, hands the result to the transceiver, and reaches the ground
 * network. Solid lines carry data and get travelling pulses; dashed lines are
 * control and simply blink. Everything draws itself as the section enters.
 */
import { useRef } from "react"

import { SectionLabel } from "@/components/brand/Brand"
import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap"

const W = 1280
const H = 470

const BOX = { rx: 10, w: 210, h: 62 }

const INPUTS = [
  { id: "link", y: 48, label: "Link Quality Estimator", sub: "SNR · elevation" },
  { id: "batt", y: 140, label: "Battery and Power Monitor", sub: "bus voltage" },
  { id: "orbit", y: 232, label: "Orbit and Pass Predictor", sub: "window · duration" },
  { id: "queue", y: 324, label: "Data Priority Queue", sub: "buffered packets" },
]

const MODES = [
  { id: "ttc", y: 96, label: "TT&C", sub: "priority 01" },
  { id: "sstv", y: 196, label: "SSTV Transmission", sub: "priority 02" },
  { id: "voice", y: 296, label: "M17 / Codec2", sub: "priority 03 · 04" },
]

const IN_X = 40
const MGR_X = 430
const MGR_Y = 158
const MGR_W = 250
const MGR_H = 150
const MODE_X = 760
const MODE_W = 180
const RF_X = 1010
const RF_Y = 158
const GS_Y = 300
/** Where the input runs turn vertical, clear of their captions. */
const INPUT_TURN_X = 382

function Box({
  x,
  y,
  w = BOX.w,
  h = BOX.h,
  label,
  sub,
  accent = false,
  className = "",
}: {
  x: number
  y: number
  w?: number
  h?: number
  label: string
  sub?: string
  accent?: boolean
  className?: string
}) {
  return (
    <g className={className}>
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={BOX.rx}
        fill={accent ? "rgba(61,107,255,0.10)" : "rgba(255,255,255,0.03)"}
        stroke={accent ? "#3d6bff" : "rgba(255,255,255,0.32)"}
        strokeWidth="1"
      />
      <text
        x={x + w / 2}
        y={sub ? y + h / 2 - 3 : y + h / 2 + 4}
        textAnchor="middle"
        fill="#ffffff"
        fontSize="14"
        fontFamily="Inter, sans-serif"
        fontWeight="500"
      >
        {label}
      </text>
      {sub && (
        <text
          x={x + w / 2}
          y={y + h / 2 + 16}
          textAnchor="middle"
          fill="#8a8f98"
          fontSize="10.5"
          fontFamily="JetBrains Mono, monospace"
          letterSpacing="1.4"
        >
          {sub.toUpperCase()}
        </text>
      )}
    </g>
  )
}

export function HowItDecides() {
  const root = useRef<HTMLElement>(null)

  useGSAP(
    () => {
      if (prefersReducedMotion()) {
        gsap.set(".arch-line, .arch-box, .arch-ctrl", { opacity: 1 })
        gsap.set(".arch-line, .arch-ctrl", { drawSVG: "100%" })
        return
      }

      const tl = gsap.timeline({
        scrollTrigger: { trigger: ".arch-figure", start: "top 80%" },
      })

      tl.from(".arch-box", {
        opacity: 0,
        y: 18,
        duration: 0.9,
        stagger: 0.09,
        ease: "power2.out",
      })
        .fromTo(
          ".arch-line",
          { drawSVG: "0%" },
          { drawSVG: "100%", duration: 1.2, stagger: 0.08, ease: "power2.inOut" },
          "-=0.25"
        )
        .fromTo(
          ".arch-ctrl",
          { drawSVG: "0%" },
          { drawSVG: "100%", duration: 1, stagger: 0.08, ease: "power2.inOut" },
          "-=0.4"
        )

      // Pulses travelling along the solid data paths, forever.
      gsap.utils.toArray<SVGPathElement>(".arch-line").forEach((path, i) => {
        const dot = document.querySelector(`.arch-pulse-${i}`)
        if (!dot) return
        gsap.set(dot, { opacity: 0 })
        gsap
          .timeline({ repeat: -1, delay: 0.9 + i * 0.28, repeatDelay: 1.1 })
          .set(dot, { opacity: 1 })
          .to(dot, {
            duration: 1.25,
            ease: "power1.inOut",
            motionPath: { path, align: path, alignOrigin: [0.5, 0.5] },
          })
          .set(dot, { opacity: 0 })
      })

      // Control lines blink.
      gsap.to(".arch-ctrl", {
        opacity: 0.25,
        duration: 1.1,
        ease: "sine.inOut",
        repeat: -1,
        yoyo: true,
        stagger: 0.2,
      })
    },
    { scope: root }
  )

  // Data paths: inputs -> manager, manager -> modes, modes -> rf, rf -> ground.
  const paths: string[] = [
    // Turn at a fixed x rather than the midpoint: the midpoint sat at 340 and
    // the edge captions run to ~350, so the vertical leg struck through them.
    ...INPUTS.map(
      (i) =>
        `M ${IN_X + BOX.w} ${i.y + BOX.h / 2} H ${INPUT_TURN_X} V ${MGR_Y + MGR_H / 2} H ${MGR_X}`
    ),
    ...MODES.map(
      (m) =>
        `M ${MGR_X + MGR_W} ${MGR_Y + MGR_H / 2} H ${(MGR_X + MGR_W + MODE_X) / 2} V ${m.y + BOX.h / 2} H ${MODE_X}`
    ),
    ...MODES.map(
      (m) =>
        `M ${MODE_X + MODE_W} ${m.y + BOX.h / 2} H ${(MODE_X + MODE_W + RF_X) / 2} V ${RF_Y + BOX.h / 2} H ${RF_X}`
    ),
    `M ${RF_X + BOX.w / 2} ${RF_Y + BOX.h} V ${GS_Y}`,
  ]

  return (
    <section
      ref={root}
      id="decides"
      data-glitch
      className="border-t border-white/[0.12] py-24 md:py-32"
    >
      <div className="shell">
        <SectionLabel>How it decides</SectionLabel>
        <div className="mt-8 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <h2
            className="max-w-[20ch] font-semibold leading-[1.06] tracking-[-0.03em]"
            style={{ fontSize: "clamp(34px, 5vw, 72px)" }}
          >
            Four readings in. One ranked queue out.
          </h2>
          <p className="max-w-[42ch] text-sm leading-[1.8] text-[#8a8f98]">
            No model weights, no training run — just thresholds the operators can
            read off a page and check against the telemetry afterwards. The same
            rules run as PL/pgSQL on the ground.
          </p>
        </div>

        <div className="arch-figure glass mt-16 overflow-x-auto rounded-[12px] p-4 md:p-8">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="h-auto w-full min-w-[900px]"
            fill="none"
          >
            {/* ---- data paths ---- */}
            {paths.map((d, i) => (
              <path
                key={i}
                className="arch-line"
                d={d}
                stroke="rgba(255,255,255,0.55)"
                strokeWidth="1.6"
                fill="none"
              />
            ))}

            {/* ---- control feedback: ground -> manager, manager -> queue ---- */}
            <path
              className="arch-ctrl"
              d={`M ${RF_X} ${GS_Y + 30} H 700 V 420 H ${MGR_X + MGR_W / 2} V ${MGR_Y + MGR_H}`}
              stroke="#3d6bff"
              strokeWidth="1.4"
              strokeDasharray="5 6"
              fill="none"
            />
            <path
              className="arch-ctrl"
              d={`M ${MGR_X} ${MGR_Y + MGR_H - 24} H ${INPUT_TURN_X + 18} V ${324 + BOX.h / 2 + 16} H ${IN_X + BOX.w}`}
              stroke="#3d6bff"
              strokeWidth="1.4"
              strokeDasharray="5 6"
              fill="none"
            />

            {/* ---- pulses ---- */}
            {paths.map((_, i) => (
              <circle
                key={i}
                className={`arch-pulse-${i}`}
                r="4.2"
                fill="#3d6bff"
                opacity="0"
              />
            ))}

            {/* ---- boxes ---- */}
            {INPUTS.map((i) => (
              <Box
                key={i.id}
                className="arch-box"
                x={IN_X}
                y={i.y}
                label={i.label}
                sub={i.sub}
              />
            ))}

            <Box
              className="arch-box"
              x={MGR_X}
              y={MGR_Y}
              w={MGR_W}
              h={MGR_H}
              label="AI-Based Autonomous Manager"
              sub="somaiyasat"
              accent
            />
            <text
              x={MGR_X + MGR_W / 2}
              y={MGR_Y + MGR_H - 26}
              textAnchor="middle"
              fill="#7f9dff"
              fontSize="10"
              fontFamily="JetBrains Mono, monospace"
              letterSpacing="1.2"
            >
              BUDGET = DURATION × LINK × 12
            </text>

            {MODES.map((m) => (
              <Box
                key={m.id}
                className="arch-box"
                x={MODE_X}
                y={m.y}
                w={MODE_W}
                label={m.label}
                sub={m.sub}
              />
            ))}

            <Box
              className="arch-box"
              x={RF_X}
              y={RF_Y}
              label="RF Transceiver"
              sub="downlink"
            />
            <Box
              className="arch-box"
              x={RF_X}
              y={GS_Y}
              h={78}
              label="Ground Station Network"
              sub="mumbai · helsinki"
              accent
            />

            {/* ---- edge captions, as Fig. 3 labels them ---- */}
            <g
              fill="#8a8f98"
              fontSize="9.5"
              fontFamily="JetBrains Mono, monospace"
              letterSpacing="1.1"
            >
              <text x={IN_X + BOX.w + 12} y={48 + BOX.h / 2 - 6}>LINK DATA</text>
              <text x={IN_X + BOX.w + 12} y={140 + BOX.h / 2 - 6}>HEALTH DATA</text>
              <text x={IN_X + BOX.w + 12} y={232 + BOX.h / 2 - 6}>TASK PRIORITY</text>
              <text x={IN_X + BOX.w + 12} y={324 + BOX.h / 2 - 6}>TASK PRIORITY</text>
              <text x={MODE_X} y={96 - 9}>TRANSMISSION COMMAND</text>
              <text x={MODE_X} y={196 - 9}>TRANSMISSION IMAGES</text>
              <text x={MODE_X} y={296 - 9}>DIGITAL VOICE AND DATA</text>
            </g>

            {/* ---- flow key ---- */}
            <g transform={`translate(${IN_X} 402)`}>
              <path d="M0 6 H30" stroke="rgba(255,255,255,0.55)" strokeWidth="1.6" />
              <path d="M38 2 L44 6 L38 10" stroke="rgba(255,255,255,0.55)" strokeWidth="1.2" fill="none" />
              <text x="52" y="10" fill="#8a8f98" fontSize="9.5"
                    fontFamily="JetBrains Mono, monospace" letterSpacing="1.1">DATA FLOW</text>
              <path d="M150 6 H180" stroke="#3d6bff" strokeWidth="1.4" strokeDasharray="5 6" />
              <path d="M188 2 L194 6 L188 10" stroke="#3d6bff" strokeWidth="1.2" fill="none" />
              <text x="202" y="10" fill="#8a8f98" fontSize="9.5"
                    fontFamily="JetBrains Mono, monospace" letterSpacing="1.1">CONTROL FLOW</text>
            </g>

            {/* ---- column captions ---- */}
            <g
              fill="#8a8f98"
              fontSize="10"
              fontFamily="JetBrains Mono, monospace"
              letterSpacing="2"
            >
              <text x={IN_X} y="26">INPUTS</text>
              <text x={MGR_X} y="26">DECISION</text>
              <text x={MODE_X} y="26">PAYLOAD MODES</text>
              <text x={RF_X} y="26">DOWNLINK</text>

            </g>
          </svg>
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {[
            {
              k: "Safe mode",
              v: "Battery under 6.8 V or link under 40 — housekeeping only.",
            },
            {
              k: "Caution band",
              v: "Battery 6.8–7.2 V — imagery is dropped, voice still flies.",
            },
            {
              k: "All clear",
              v: "Above 7.2 V with a healthy link — every mode competes for the budget.",
            },
          ].map((r) => (
            <div key={r.k} className="border-t border-white/[0.12] pt-5">
              <p className="mono-label text-[#3d6bff]">{r.k}</p>
              <p className="mt-3 text-sm leading-[1.75] text-[#8a8f98]">{r.v}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
