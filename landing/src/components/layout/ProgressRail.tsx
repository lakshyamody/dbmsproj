/**
 * A thin progress rail down the left edge: how far through the page you are,
 * which section you are in, and a clickable tick per section.
 *
 * Sits opposite the right-edge SideTab so the two never collide. Only shown
 * when the left gutter is genuinely wide enough (see MIN_WIDTH), and never
 * under prefers-reduced-motion.
 */
import { useEffect, useRef, useState } from "react"

import { gsap, ScrollTrigger, useGSAP, prefersReducedMotion } from "@/lib/gsap"
import { scrollToId } from "@/lib/lenis"

/** Narrower than this and the rail would overlap the headings. */
const MIN_WIDTH = 1600

/** Matches the section ids already present in the DOM. */
const SECTIONS = [
  { id: "hero", label: "Hero" },
  { id: "mission", label: "Mission" },
  { id: "challenge", label: "Challenge" },
  { id: "payloads", label: "Payloads" },
  { id: "build", label: "Build" },
  { id: "decides", label: "Decides" },
  { id: "numbers", label: "Numbers" },
  { id: "network", label: "Network" },
  { id: "team", label: "Team" },
  { id: "cta", label: "Live" },
]

export function ProgressRail({ ready }: { ready: boolean }) {
  const root = useRef<HTMLDivElement>(null)
  const fill = useRef<HTMLSpanElement>(null)
  const [active, setActive] = useState(0)
  const [enabled, setEnabled] = useState(false)

  // The rail lives in the left gutter. `.shell` is max-w-1440 with a 72px
  // inset, so below ~1600px there is no gutter left and the rail would sit on
  // top of the headings. Measured, not guessed.
  useEffect(() => {
    if (prefersReducedMotion()) return
    const check = () => setEnabled(window.innerWidth >= MIN_WIDTH)
    check()
    window.addEventListener("resize", check)
    return () => window.removeEventListener("resize", check)
  }, [])

  useGSAP(
    () => {
      if (!enabled || !ready) return

      // Overall page progress drives the fill height.
      const progress = ScrollTrigger.create({
        start: 0,
        end: "max",
        onUpdate: (self) => {
          if (fill.current) {
            fill.current.style.transform = `scaleY(${self.progress})`
          }
        },
      })

      // One trigger per section decides which tick is lit. `Payloads` renders
      // two different roots depending on viewport, so query defensively.
      const triggers = SECTIONS.map((s, i) => {
        const el = document.getElementById(s.id)
        if (!el) return null
        return ScrollTrigger.create({
          trigger: el,
          start: "top 55%",
          end: "bottom 55%",
          onToggle: (self) => {
            if (self.isActive) setActive(i)
          },
        })
      }).filter(Boolean) as ScrollTrigger[]

      return () => {
        progress.kill()
        triggers.forEach((t) => t.kill())
      }
    },
    { scope: root, dependencies: [enabled, ready] }
  )

  // Fade the whole rail in once the intro has handed off.
  useGSAP(
    () => {
      if (!enabled || !ready || !root.current) return
      gsap.fromTo(
        root.current,
        { opacity: 0, x: -8 },
        { opacity: 1, x: 0, duration: 1, ease: "power2.out", delay: 0.4 }
      )
    },
    { dependencies: [enabled, ready] }
  )

  if (!enabled) return null

  return (
    <div
      ref={root}
      className="fixed left-0 top-1/2 z-40 block -translate-y-1/2 pl-4 opacity-0"
      aria-hidden="true"
    >
      <div className="flex items-center gap-3">
        {/* the rail */}
        <div className="relative h-[220px] w-px bg-white/[0.14]">
          <span
            ref={fill}
            className="absolute inset-x-0 top-0 block h-full origin-top bg-[#3d6bff]"
            style={{ transform: "scaleY(0)" }}
          />
        </div>

        {/* ticks + current section */}
        <ul className="flex flex-col gap-[7px]">
          {SECTIONS.map((s, i) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => scrollToId(s.id)}
                className="group flex items-center gap-2 outline-none"
                tabIndex={-1}
              >
                <span
                  className={`block h-px transition-all duration-500 ${
                    i === active ? "w-5 bg-[#3d6bff]" : "w-2.5 bg-white/25"
                  }`}
                />
                <span
                  className={`mono-label whitespace-nowrap transition-all duration-500 ${
                    i === active
                      ? "translate-x-0 text-white opacity-100"
                      : "-translate-x-1 text-[#8a8f98] opacity-0 group-hover:opacity-70"
                  }`}
                >
                  {s.label}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
