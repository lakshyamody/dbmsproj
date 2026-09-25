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
    // The two below are real, not modelled: live orbital element sets and the
    // pass windows SGP4 computes from them.
    { k: "Real satellites tracked", v: t.tracked_objects, sub: "live CelesTrak element sets" },
    { k: "Real passes computed", v: t.tracked_passes, sub: "SGP4 over the station network" },
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

    },
    // stats.source is the reliable signal that real data has arrived: it goes
    // "fallback" -> "database" exactly once. Depending on t.packets alone was
    // not enough -- the fallback snapshot was taken from this same database, so
    // that number is identical either way, the effect never re-ran, and every
    // counter animated to its fallback target instead of the fetched one.
    { scope: root, dependencies: [stats.source, t.packets, t.tracked_objects] }
  )

  // The card entrance is deliberately a SEPARATE effect with no data
  // dependency. It is a gsap.from(opacity: 0), so re-running it after its
  // ScrollTrigger has already been passed re-hides the cards and never plays
  // them back in -- which is exactly what happened when it shared the effect
  // above and that effect started re-running on new data.
  useGSAP(
    () => {
      if (prefersReducedMotion()) return
      gsap.from(".counter-card", {
        opacity: 0,
        y: 40,
        duration: 1.35,
        stagger: 0.15,
        ease: "power2.out",
        scrollTrigger: { trigger: ".counter-grid", start: "top 90%" },
      })
    },
    { scope: root, dependencies: [] }
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

        <div className="counter-grid mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
        {t.tracked_objects > 0 && (
          <p className="mt-3 max-w-[62ch] text-[13px] leading-relaxed text-[#8a8f98]">
            The first four counters describe the proposed mission. The last two are
            real: {t.tracked_objects} amateur-radio satellites currently in orbit,
            propagated from published orbital element sets, whose pass windows the
            same ground-station software plans against.
          </p>
        )}
      </div>
    </section>
  )
}
