/** [ THE MISSION ] — the thesis, a small rotating Earth, and the constraints. */
import { useRef } from "react"

import { SectionLabel } from "@/components/brand/Brand"
import { MiniEarth } from "@/components/three/MiniEarth"
import { gsap, useGSAP, SplitText, prefersReducedMotion } from "@/lib/gsap"

export function Mission() {
  const root = useRef<HTMLElement>(null)

  useGSAP(
    () => {
      const reduced = prefersReducedMotion()
      const heading = root.current?.querySelector(".mission-heading")
      if (!heading) return

      if (reduced) {
        gsap.set(heading, { opacity: 1 })
        return
      }

      const split = new SplitText(heading as HTMLElement, { type: "words,lines" })
      gsap.set(heading, { opacity: 1 })
      gsap.from(split.words, {
        opacity: 0.12,
        y: 18,
        duration: 1.15,
        stagger: 0.05,
        ease: "power2.out",
        scrollTrigger: { trigger: heading, start: "top 85%" },
      })

      gsap.from(".mission-note", {
        opacity: 0,
        y: 22,
        duration: 1.4,
        stagger: 0.18,
        ease: "power2.out",
        scrollTrigger: { trigger: ".mission-notes", start: "top 88%" },
      })

      gsap.from(".mission-globe", {
        opacity: 0,
        scale: 0.9,
        duration: 1.6,
        ease: "power2.out",
        scrollTrigger: { trigger: ".mission-globe", start: "top 90%" },
      })

      return () => split.revert()
    },
    { scope: root }
  )

  return (
    <section
      ref={root}
      id="mission"
      data-glitch
      className="relative border-t border-white/[0.12] py-24 md:py-36"
    >
      <div className="shell">
        <SectionLabel>The mission</SectionLabel>

        <h2
          className="mission-heading mx-auto mt-10 max-w-[22ch] text-balance text-center font-semibold leading-[1.06] tracking-[-0.03em] opacity-0"
          style={{ fontSize: "clamp(36px, 5.4vw, 76px)" }}
        >
          Tiny satellites get minutes of contact a day.
          <br />
          Ours decides what matters most.
        </h2>

        <MiniEarth className="mission-globe mx-auto mt-16 h-[320px] w-full max-w-[520px] md:h-[400px]" />

        <div className="mission-notes mx-auto mt-16 grid max-w-5xl gap-10 md:grid-cols-3">
          <div className="mission-note">
            <p className="mono-label text-[#3d6bff]">Power</p>
            <p className="mt-3 text-sm leading-[1.75] text-[#8a8f98]">
              A PocketQube runs on what its faces can collect — here, five
              42&nbsp;×&nbsp;23&nbsp;mm cells on a 127&nbsp;mm stack. The radio
              is the hungriest thing aboard, so every transmission is spent from
              a budget that has to last the orbit.
            </p>
          </div>
          <div className="mission-note">
            <p className="mono-label text-[#3d6bff]">Bandwidth</p>
            <p className="mt-3 text-sm leading-[1.75] text-[#8a8f98]">
              The downlink is measured in kilobits and shared by four modes over
              one RF front end. A single slow-scan image outweighs a day of
              housekeeping, so sending one means not sending the other.
            </p>
          </div>
          <div className="mission-note">
            <p className="mono-label text-[#3d6bff]">Pass windows</p>
            <p className="mt-3 text-sm leading-[1.75] text-[#8a8f98]">
              In low Earth orbit the spacecraft clears the horizon for six to
              ten minutes at a time. Whatever is not sent in that window waits
              for the next orbit — or is never sent at all. Everything it does
              downlink is open to the amateur radio community.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
