/** [ BY THE NUMBERS ] — four counters that count up on enter, from stats.json. */
import { useRef } from "react"

import { SectionLabel } from "@/components/brand/Brand"
import { Card } from "@/components/ui/card"
import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap"
import type { Stats } from "@/hooks/useStats"

export function ByTheNumbers({ stats }: { stats: Stats }) {
  const root = useRef<HTMLElement>(null)
  const t = stats.totals

  const CARDS = [
    { k: "Satellites deployed", v: t.deployed_satellites, sub: `of ${t.satellites} in the fleet` },
    { k: "Telemetry packets", v: t.packets, sub: `${t.unsent_packets.toLocaleString()} still queued` },
    { k: "Passes planned", v: t.passes, sub: `across ${t.ground_stations} ground stations` },
    { k: "Payload modes", v: t.payload_modes, sub: "ranked by priority" },
  ]

  useGSAP(
    () => {
      const reduced = prefersReducedMotion()

      gsap.utils.toArray<HTMLElement>(".counter-value").forEach((el) => {
        const target = Number(el.dataset.value ?? 0)
        if (reduced) {
          el.textContent = target.toLocaleString()
          return
        }
        const obj = { n: 0 }
        gsap.to(obj, {
          n: target,
          duration: 2.4,
          ease: "power2.out",
          scrollTrigger: { trigger: el, start: "top 92%" },
          onUpdate: () => {
            el.textContent = Math.round(obj.n).toLocaleString()
          },
        })
      })

      if (reduced) return
      gsap.from(".counter-card", {
        opacity: 0,
        y: 40,
        duration: 1.35,
        stagger: 0.15,
        ease: "power2.out",
        scrollTrigger: { trigger: ".counter-grid", start: "top 90%" },
      })
    },
    { scope: root, dependencies: [t.packets] }
  )

  return (
    <section
      ref={root}
      id="numbers"
      data-glitch
      className="border-t border-white/[0.12] py-24 md:py-32"
    >
      <div className="shell">
        <SectionLabel>By the numbers</SectionLabel>
        <h2
          className="mt-8 max-w-[22ch] font-semibold leading-[1.06] tracking-[-0.03em]"
          style={{ fontSize: "clamp(34px, 5vw, 72px)" }}
        >
          Everything on this page is read from the database.
        </h2>

        <div className="counter-grid mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {CARDS.map((c) => (
            <Card key={c.k} className="counter-card gap-0 px-7 py-8">
              <span
                className="counter-value block font-mono leading-none tabular-nums text-white"
                data-value={c.v}
                style={{ fontSize: "clamp(40px, 4.4vw, 60px)" }}
              >
                0
              </span>
              <span className="mono-label mt-5 block text-white">{c.k}</span>
              <span className="mt-2 block text-[13px] text-[#8a8f98]">{c.sub}</span>
            </Card>
          ))}
        </div>

        <p className="mono-label mt-8 text-[#8a8f98]">
          Source: {stats.source === "database" ? "live PostgreSQL" : stats.source} ·
          exported by scripts/export_stats.py
        </p>
      </div>
    </section>
  )
}
