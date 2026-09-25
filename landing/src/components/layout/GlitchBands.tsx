/**
 * Section-enter glitch: two or three blurred horizontal bands sweep across the
 * viewport when a new section comes into view. Deliberately brief — it should
 * register as a transition artefact, not an effect.
 */
import { useRef } from "react"

import { gsap, useGSAP, ScrollTrigger, prefersReducedMotion } from "@/lib/gsap"

export function GlitchBands() {
  const root = useRef<HTMLDivElement>(null)

  useGSAP(
    () => {
      if (prefersReducedMotion()) return

      const bands = gsap.utils.toArray<HTMLElement>(".glitch-band")
      const fire = () => {
        bands.forEach((b, i) => {
          const fromLeft = i % 2 === 0
          gsap.set(b, {
            top: `${12 + Math.random() * 68}%`,
            height: 20 + Math.random() * 40,
            xPercent: fromLeft ? -110 : 110,
            opacity: 0.5 + Math.random() * 0.35,
          })
          gsap.to(b, {
            xPercent: fromLeft ? 110 : -110,
            duration: 0.42 + Math.random() * 0.22,
            ease: "power2.inOut",
            delay: i * 0.055,
            onComplete: () => gsap.set(b, { opacity: 0 }),
          })
        })
      }

      const triggers = gsap.utils
        .toArray<HTMLElement>("section[data-glitch]")
        .map((s) =>
          ScrollTrigger.create({
            trigger: s,
            start: "top 72%",
            onEnter: fire,
          })
        )

      return () => triggers.forEach((t) => t.kill())
    },
    { scope: root }
  )

  return (
    <div
      ref={root}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[45] overflow-hidden"
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="glitch-band absolute left-0 w-full opacity-0"
          style={{
            background:
              i === 1
                ? "linear-gradient(90deg, transparent, rgba(255,255,255,.5), transparent)"
                : "linear-gradient(90deg, transparent, rgba(61,107,255,.6), transparent)",
            filter: "blur(9px)",
          }}
        />
      ))}
    </div>
  )
}
