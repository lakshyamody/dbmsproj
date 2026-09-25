/**
 * The pinned hero: ~500vh of scroll (300vh on phones) scrubbing four scenes,
 * with a fixed headline in the bottom-left that fills in as scene 1 plays.
 */
import { useMemo, useRef } from "react"

import { HeroScene } from "@/components/three/HeroScene"
import { SectionLabel } from "@/components/brand/Brand"
import {
  gsap,
  ScrollTrigger,
  SplitText,
  useGSAP,
  prefersReducedMotion,
  isMobileViewport,
} from "@/lib/gsap"
import type { SceneProgress } from "@/hooks/useScrollScene"

const SCENE_CAPTIONS = [
  { at: 0.02, text: "ORBIT SHELLS · 3 DEPLOYED CUBES" },
  { at: 0.3, text: "APPROACH · KJSSE GROUND STATION" },
  { at: 0.55, text: "DEPLOYMENT CONFIRMED · SYS_INIT COMPLETE" },
  { at: 0.78, text: "LINK ACQUIRED · ROUTING BY PRIORITY" },
]

export function Hero({ ready }: { ready: boolean }) {
  const section = useRef<HTMLElement>(null)
  const headline = useRef<HTMLDivElement>(null)
  const line2 = useRef<HTMLSpanElement>(null)
  const caption = useRef<HTMLSpanElement>(null)

  const reduced = useMemo(() => prefersReducedMotion(), [])
  const mobile = useMemo(() => isMobileViewport(), [])

  // Shared, mutable scroll state handed to the canvas.
  const progressRef = useRef<SceneProgress>({ current: 0, visible: false })

  useGSAP(
    () => {
      if (!ready) return
      // The gate has handed off: let the hero canvas draw again.
      progressRef.current.visible = true

      // ---- headline reveal, line by line -------------------------------
      const split = new SplitText(".hero-line", { type: "lines", linesClass: "hero-split-line" })
      gsap.set(split.lines, { yPercent: 110 })
      gsap.to(split.lines, {
        yPercent: 0,
        duration: 1.15,
        stagger: 0.12,
        ease: "expo.out",
      })
      gsap.fromTo(
        ".hero-sub",
        { opacity: 0, y: 14 },
        { opacity: 1, y: 0, duration: 0.9, delay: 0.5 }
      )
      gsap.fromTo(
        ".hero-scroll-hint",
        { opacity: 0 },
        { opacity: 1, duration: 0.8, delay: 1.1 }
      )

      if (reduced) {
        // No pinning, no scrub: show the first scene and let the page flow.
        progressRef.current.current = 0.04
        ScrollTrigger.refresh()
        return () => split.revert()
      }

      // ---- the pinned scrub ---------------------------------------------
      const st = ScrollTrigger.create({
        trigger: section.current,
        start: "top top",
        end: "bottom bottom",
        pin: ".hero-stage",
        pinSpacing: false,
        scrub: true,
        onUpdate: (self) => {
          progressRef.current.current = self.progress
        },
        onToggle: (self) => {
          progressRef.current.visible = self.isActive
        },
      })

      // Line 2 fills from dim to white during scene 1.
      gsap.fromTo(
        line2.current,
        { opacity: 0.3 },
        {
          opacity: 1,
          ease: "none",
          scrollTrigger: {
            trigger: section.current,
            start: "top top",
            end: "18% top",
            scrub: true,
          },
        }
      )

      // Headline drifts out as the line-art scene takes over.
      gsap.to(headline.current, {
        opacity: 0,
        y: -30,
        ease: "none",
        scrollTrigger: {
          trigger: section.current,
          start: "38% top",
          end: "48% top",
          scrub: true,
        },
      })

      // Mono caption swaps as each scene establishes.
      const capTick = () => {
        if (!caption.current) return
        const p = progressRef.current.current
        let text = SCENE_CAPTIONS[0].text
        for (const c of SCENE_CAPTIONS) if (p >= c.at) text = c.text
        if (caption.current.textContent !== text) caption.current.textContent = text
      }
      gsap.ticker.add(capTick)

      // Every other ScrollTrigger on the page was created before the hero's
      // pin existed, and the gate overlay has just unmounted. Refresh once,
      // here: we are at y=0 with no pin engaged and still behind an opaque
      // overlay, which is the only safe moment to re-measure.
      ScrollTrigger.refresh()

      return () => {
        split.revert()
        st.kill()
        gsap.ticker.remove(capTick)
      }
    },
    { scope: section, dependencies: [ready, reduced] }
  )

  const heroVh = reduced ? 100 : mobile ? 300 : 500

  return (
    <section
      ref={section}
      id="hero"
      className="relative w-full"
      style={{ height: `${heroVh}vh` }}
    >
      <div className="hero-stage relative h-screen w-full overflow-hidden">
        {/* 3D + line art */}
        <HeroScene progressRef={progressRef} ready={ready} />

        {/* vignette so text always clears the imagery */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 90% at 50% 40%, transparent 30%, rgba(0,0,0,0.55) 78%, #000 100%)",
          }}
        />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[46vh] bg-gradient-to-t from-black via-black/75 to-transparent" />

        {/* headline, bottom-left */}
        <div
          ref={headline}
          className="shell pointer-events-none absolute inset-x-0 bottom-0 pb-[6vh] md:pb-[8vh]"
        >
          <div className="mb-5 flex items-center gap-4">
            <SectionLabel accent>
              <span ref={caption}>ORBIT SHELLS · 3 DEPLOYED CUBES</span>
            </SectionLabel>
          </div>

          <h1
            className="max-w-[16ch] font-semibold leading-[0.92] tracking-[-0.035em]"
            style={{ fontSize: "clamp(48px, 7.6vw, 110px)" }}
          >
            <span className="hero-line block overflow-hidden">Small satellite.</span>
            <span className="hero-line block overflow-hidden">
              <span ref={line2} className="inline-block opacity-30">
                Smart decisions.
              </span>
            </span>
          </h1>

          <p
            className="hero-sub mt-7 max-w-[64ch] font-mono text-[11px] uppercase tracking-[0.16em] text-[#8a8f98] opacity-0"
            style={{ lineHeight: 1.9 }}
          >
            A PocketQube mission by K J Somaiya · SomaiyaPod deployer · onboard
            autonomous routing · open to the amateur radio community.
          </p>
        </div>

        {/* scroll hint */}
        <div className="hero-scroll-hint pointer-events-none absolute bottom-[6vh] right-6 opacity-0 md:right-12">
          <div className="flex flex-col items-center gap-3">
            <span className="mono-label rotate-90 text-[#8a8f98]">SCROLL</span>
            <span className="mt-6 block h-14 w-px bg-gradient-to-b from-white/50 to-transparent" />
          </div>
        </div>
      </div>
    </section>
  )
}
