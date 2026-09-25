/** Closing call to action, over the glowing limb. */
import { useRef } from "react"

import { Button } from "@/components/ui/button"
import { SectionLabel } from "@/components/brand/Brand"
import { HorizonEarth } from "@/components/three/HorizonEarth"
import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap"
import { DASHBOARD_URL } from "@/lib/config"

export function CTA() {
  const root = useRef<HTMLElement>(null)

  useGSAP(
    () => {
      if (prefersReducedMotion()) return
      gsap.from(".cta-item", {
        opacity: 0,
        y: 34,
        duration: 1.4,
        stagger: 0.16,
        ease: "power2.out",
        scrollTrigger: { trigger: root.current, start: "top 82%" },
      })
    },
    { scope: root }
  )

  return (
    <section
      ref={root}
      id="cta"
      data-glitch
      className="relative flex min-h-[86vh] items-center overflow-hidden border-t border-white/[0.12]"
    >
      <HorizonEarth className="absolute inset-x-0 bottom-0 h-[70%]" />

      <div className="shell relative z-10 w-full py-28 text-center">
        <div className="cta-item flex justify-center">
          <SectionLabel accent>Live now</SectionLabel>
        </div>

        <h2
          className="cta-item mx-auto mt-8 max-w-[14ch] font-semibold leading-[0.98] tracking-[-0.035em]"
          style={{ fontSize: "clamp(42px, 7vw, 96px)" }}
        >
          See the mission live.
        </h2>

        <p className="cta-item mx-auto mt-7 max-w-[54ch] text-[15px] leading-[1.8] text-[#8a8f98]">
          The dashboard runs against the same PostgreSQL database this page reads
          from — the globe, the pass planner and every permission check are real.
        </p>

        <div className="cta-item mt-12">
          <Button asChild size="lg" className="mono-label">
            <a href={DASHBOARD_URL} target="_blank" rel="noreferrer">
              Enter Mission Control →
            </a>
          </Button>
        </div>

        <p className="cta-item mono-label mt-8 text-[#8a8f98]">
          Runs locally on :8501
        </p>
      </div>
    </section>
  )
}
