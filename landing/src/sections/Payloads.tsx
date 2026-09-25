/**
 * [ PAYLOADS ] — pinned. The icon on the left crossfades between the four
 * modes while the copy, badge and packet count swap on the right, and a
 * progress bar walks 1/4 -> 4/4.
 *
 * Packet counts come from stats.json, so the page shows the real queue.
 */
import { useMemo, useRef, useState } from "react"

import { SectionLabel } from "@/components/brand/Brand"
import { PAYLOAD_ICONS } from "@/components/brand/PayloadIcons"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { PAYLOAD_META } from "@/lib/palette"
import { gsap, useGSAP, ScrollTrigger, prefersReducedMotion, isMobileViewport } from "@/lib/gsap"
import type { Stats } from "@/hooks/useStats"

export function Payloads({ stats }: { stats: Stats }) {
  const root = useRef<HTMLElement>(null)
  const [active, setActive] = useState(0)
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const mobile = useMemo(() => isMobileViewport(), [])

  const modes = useMemo(
    () =>
      [...stats.payloads].sort((a, b) => a.priority - b.priority).map((p) => ({
        ...p,
        meta: PAYLOAD_META[p.payload_type] ?? {
          label: p.payload_type,
          blurb: p.description,
          priority: p.priority,
        },
      })),
    [stats.payloads]
  )

  useGSAP(
    () => {
      if (reduced || mobile || modes.length === 0) return

      const st = ScrollTrigger.create({
        trigger: root.current,
        start: "top top",
        end: `+=${modes.length * 68}%`,
        pin: ".payload-stage",
        pinSpacing: true,
        scrub: false,
        onUpdate: (self) => {
          const i = Math.min(
            modes.length - 1,
            Math.floor(self.progress * modes.length * 0.999)
          )
          setActive(i)
        },
      })
      return () => st.kill()
    },
    { scope: root, dependencies: [modes.length, reduced, mobile] }
  )

  // Only the flourish is GSAP's. Opacity is driven by React inline style +
  // a CSS transition: useGSAP's scope cleanup reverts inline styles when
  // `active` changes, which fought a GSAP-driven fade and left previously
  // shown icons stacked on top of each other.
  useGSAP(
    () => {
      if (reduced) return
      // Matches the opacity delay below, so the icon actually moves as it
      // appears instead of finishing its motion while still invisible.
      gsap.fromTo(
        `.payload-icon-${active}`,
        { scale: 0.92, rotate: -4 },
        { scale: 1, rotate: 0, duration: 0.75, delay: 0.13, ease: "power3.out" }
      )
      gsap.fromTo(
        ".payload-copy > *",
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.5, stagger: 0.06, ease: "power2.out" }
      )
    },
    { scope: root, dependencies: [active, reduced, modes.length] }
  )

  if (modes.length === 0) return null

  const current = modes[active]

  /* ---- stacked layout on phones: every mode listed, no pin ---- */
  if (mobile || reduced) {
    return (
      <section
        ref={root}
        id="payloads"
        data-glitch
        className="border-t border-white/[0.12] py-24"
      >
        <div className="shell">
          <SectionLabel>Payloads</SectionLabel>
          <h2 className="mt-8 max-w-[18ch] text-[34px] font-semibold leading-[1.08] tracking-[-0.03em]">
            Four things to say. Never enough time to say them all.
          </h2>

          <div className="mt-12 flex flex-col gap-8">
            {modes.map((m) => {
              const I = PAYLOAD_ICONS[m.payload_type] ?? PAYLOAD_ICONS["TT&C"]
              return (
                <div
                  key={m.payload_type}
                  className="glass rounded-[12px] p-6"
                >
                  <I className="h-24 w-24 text-white" />
                  <div className="mt-5 flex items-center gap-3">
                    <h3 className="text-2xl font-semibold">{m.meta.label}</h3>
                    <Badge>Priority {String(m.priority).padStart(2, "0")}</Badge>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-[#8a8f98]">
                    {m.meta.blurb}
                  </p>
                  <p className="mono-label mt-4 text-white">
                    {m.packet_count.toLocaleString()} packets
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      </section>
    )
  }

  /* ---- pinned layout ---- */
  return (
    <section
      ref={root}
      id="payloads"
      data-glitch
      className="relative border-t border-white/[0.12]"
    >
      <div className="payload-stage relative flex h-screen items-center overflow-hidden">
        <div className="shell w-full">
          <SectionLabel>Payloads</SectionLabel>

          <div className="mt-10 grid items-center gap-16 md:grid-cols-[minmax(0,0.85fr)_minmax(0,1fr)]">
            {/* icon column */}
            <div className="relative flex h-[320px] items-center justify-center md:h-[400px]">
              {modes.map((m, i) => {
                const I = PAYLOAD_ICONS[m.payload_type] ?? PAYLOAD_ICONS["TT&C"]
                return (
                  <div
                    key={m.payload_type}
                    className={`payload-icon-${i} pointer-events-none absolute h-[260px] w-[260px] md:h-[330px] md:w-[330px]`}
                    // Two dense white line drawings crossfading on top of each
                    // other read as a jumble. Drop the outgoing one quickly,
                    // then bring the incoming one in, so they barely overlap.
                    style={{
                      opacity: i === active ? 1 : 0,
                      transitionProperty: "opacity",
                      transitionTimingFunction: "ease-out",
                      transitionDuration: i === active ? "260ms" : "140ms",
                      transitionDelay: i === active ? "130ms" : "0ms",
                    }}
                  >
                    <I className="h-full w-full text-white" />
                  </div>
                )
              })}
              {/* faint ring behind the icon */}
              <div
                className="pointer-events-none absolute -z-10 h-[380px] w-[380px] rounded-full border border-white/[0.08]"
                style={{
                  background:
                    "radial-gradient(circle, rgba(61,107,255,.10), transparent 62%)",
                }}
              />
            </div>

            {/* copy column */}
            <div>
              <div className="payload-copy">
                <div className="flex flex-wrap items-center gap-4">
                  <h3
                    className="font-semibold leading-none tracking-[-0.03em]"
                    style={{ fontSize: "clamp(38px, 5vw, 68px)" }}
                  >
                    {current.meta.label}
                  </h3>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span>
                        <Badge>
                          Priority {String(current.priority).padStart(2, "0")}
                        </Badge>
                      </span>
                    </TooltipTrigger>
                    <TooltipContent side="right">
                      Lower number wins the downlink first
                    </TooltipContent>
                  </Tooltip>
                </div>

                <p className="mt-6 max-w-[46ch] text-[16px] leading-[1.8] text-[#8a8f98]">
                  {current.meta.blurb}
                </p>

                <div className="mt-10 flex flex-wrap items-end gap-10">
                  <div>
                    <p className="mono-label text-[#8a8f98]">Packets on record</p>
                    <p className="mt-2 font-mono text-[44px] leading-none tabular-nums text-white">
                      {current.packet_count.toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="mono-label text-[#8a8f98]">Still queued</p>
                    <p className="mt-2 font-mono text-[44px] leading-none tabular-nums text-[#3d6bff]">
                      {current.unsent_count.toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>

              {/* progress through the four modes */}
              <div className="mt-14">
                <div className="mb-3 flex items-center justify-between">
                  <span className="mono-label text-[#8a8f98]">
                    {String(active + 1).padStart(2, "0")} / {String(modes.length).padStart(2, "0")}
                  </span>
                  <div className="flex gap-4">
                    {modes.map((m, i) => (
                      <span
                        key={m.payload_type}
                        className={`mono-label transition-colors duration-300 ${
                          i === active ? "text-white" : "text-white/25"
                        }`}
                      >
                        {m.meta.label}
                      </span>
                    ))}
                  </div>
                </div>
                <Progress value={((active + 1) / modes.length) * 100} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
