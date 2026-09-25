/**
 * The intro gate: a spiral animation on black that holds the page until the
 * visitor asks to go in.
 *
 * It is an overlay, not a section above the hero — the hero pins via a global
 * `.hero-stage` selector with `pinSpacing: false`, and every other
 * ScrollTrigger on the page is measured from a document that starts at the
 * hero. Adding real height above it would move all of those. A fixed overlay
 * is out of flow, so nothing else has to know it exists.
 *
 * Because scroll stays locked, "scroll down" is detected as a *gesture*
 * (wheel / swipe / key) rather than as an actual scroll event.
 */
import { useEffect, useRef, useState } from "react"

import { SpiralAnimation } from "@/components/ui/spiral-animation"
import { Wordmark } from "@/components/brand/Brand"
import { gsap, prefersReducedMotion } from "@/lib/gsap"
import { startScroll, stopScroll } from "@/lib/lenis"

/** Textures the hero needs warm. stats.json is deliberately not preloaded: */
/** useStats fetches it with a different cache mode, so it would be dead weight. */
const ASSETS = [
  "assets/textures/earth_day.jpg",
  "assets/textures/earth_night.jpg",
  "assets/textures/land_mask.png",
]

/** How long the spiral gets to establish itself before the cue appears. */
const ESTABLISH_MS = 2200
/** Hard ceiling: reveal the cue even if an asset never resolves. */
const BAIL_MS = 9000

export function IntroGate({ onDone }: { onDone: () => void }) {
  const root = useRef<HTMLDivElement>(null)
  const [gone, setGone] = useState(false)

  // Held in a ref so the effect below can keep empty deps. App re-renders when
  // useStats resolves, and an inline-arrow prop would otherwise re-run the
  // whole gate — restarting the timer and releasing scroll early.
  const onDoneRef = useRef(onDone)
  useEffect(() => {
    onDoneRef.current = onDone
  })

  useEffect(() => {
    const el = root.current
    if (!el) return

    const reduced = prefersReducedMotion()
    const cue = el.querySelector<HTMLElement>(".intro-cue")
    const button = el.querySelector<HTMLButtonElement>(".intro-enter")
    const canvasWrap = el.querySelector<HTMLElement>(".intro-canvas")
    const mark = el.querySelector<HTMLElement>(".intro-mark")

    // A mid-page reload would otherwise restore scroll to where you were, and
    // then the gate would lock you there and hand off to a hero that thinks it
    // is already half-scrubbed.
    if ("scrollRestoration" in history) history.scrollRestoration = "manual"
    window.scrollTo(0, 0)
    stopScroll()

    const started = performance.now()
    let loaded = 0
    let revealed = false
    let dismissed = false
    let tl: gsap.core.Timeline | null = null

    ASSETS.forEach((path) => {
      const img = new Image()
      const bump = () => {
        loaded++
      }
      img.onload = bump
      img.onerror = bump
      img.src = `${import.meta.env.BASE_URL}${path}`
    })

    // ---- reveal the cue -------------------------------------------------
    function reveal() {
      if (revealed) return
      revealed = true
      gsap.ticker.remove(gate)
      window.clearTimeout(bail)

      if (!cue) {
        armed = true
        return
      }
      gsap.to(cue, {
        opacity: 1,
        y: 0,
        duration: reduced ? 0.2 : 0.9,
        ease: "power2.out",
        // Not auto-focused: the window-level key listener below already gives
        // keyboard users Space / Enter / ArrowDown, and programmatic focus
        // draws a focus ring around the cue that reads as a stray box.
        onComplete: () => {
          armed = true
        },
      })
    }

    let armed = false
    const establish = reduced ? 400 : ESTABLISH_MS

    const gate = () => {
      const elapsed = performance.now() - started
      if ((loaded >= ASSETS.length && elapsed >= establish) || elapsed >= BAIL_MS) {
        reveal()
      }
    }
    gsap.ticker.add(gate)
    const bail = window.setTimeout(reveal, BAIL_MS)

    // ---- dismiss --------------------------------------------------------
    function dismiss() {
      if (dismissed || !root.current) return
      dismissed = true
      detach()

      tl = gsap.timeline({
        onComplete: () => {
          startScroll()
          setGone(true)
        },
      })

      // Hand off FIRST, while the overlay is still fully opaque: Hero mounts
      // its ScrollTriggers and resumes its canvas during the dissolve, unseen.
      tl.call(() => onDoneRef.current())

      if (reduced) {
        tl.to(root.current, { opacity: 0, duration: 0.3, ease: "power1.out" })
        return
      }

      if (canvasWrap) {
        tl.to(canvasWrap, { scale: 1.18, opacity: 0, duration: 1, ease: "power2.in" }, 0)
      }
      if (cue) tl.to(cue, { opacity: 0, y: -10, duration: 0.3 }, 0)
      if (mark) tl.to(mark, { opacity: 0, duration: 0.35 }, 0)
      tl.to(root.current, { opacity: 0, duration: 0.55, ease: "power2.inOut" }, 0.45)
    }

    // ---- intent listeners ------------------------------------------------
    const onWheel = (e: WheelEvent) => {
      if (armed && Math.abs(e.deltaY) > 8) dismiss()
    }
    let touchStartY = 0
    const onTouchStart = (e: TouchEvent) => {
      touchStartY = e.touches[0]?.clientY ?? 0
    }
    const onTouchMove = (e: TouchEvent) => {
      if (!armed) return
      const y = e.touches[0]?.clientY ?? 0
      if (touchStartY - y > 24) dismiss()
    }
    const onKey = (e: KeyboardEvent) => {
      if (!armed) return
      if (e.key === " " || e.key === "ArrowDown" || e.key === "PageDown" || e.key === "Enter") {
        e.preventDefault()
        dismiss()
      }
    }
    const onClick = () => dismiss()

    function detach() {
      window.removeEventListener("wheel", onWheel)
      window.removeEventListener("touchstart", onTouchStart)
      window.removeEventListener("touchmove", onTouchMove)
      window.removeEventListener("keydown", onKey)
      button?.removeEventListener("click", onClick)
    }

    window.addEventListener("wheel", onWheel, { passive: true })
    window.addEventListener("touchstart", onTouchStart, { passive: true })
    window.addEventListener("touchmove", onTouchMove, { passive: true })
    window.addEventListener("keydown", onKey)
    button?.addEventListener("click", onClick)

    return () => {
      detach()
      gsap.ticker.remove(gate)
      window.clearTimeout(bail)
      tl?.kill()
      // Unconditional: html.lenis-stopped sets overflow:hidden, so if anything
      // above threw, this is what stops the page being permanently unscrollable.
      startScroll()
    }
  }, [])

  if (gone) return null

  const reduced = prefersReducedMotion()

  return (
    <div
      ref={root}
      className="fixed inset-0 z-[100] overflow-hidden bg-black"
      role="dialog"
      aria-modal="true"
      aria-label="Intro"
    >
      {!reduced && (
        <div className="intro-canvas absolute inset-0">
          <SpiralAnimation />
        </div>
      )}

      {/* keeps text clear of the densest part of the field */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(70% 50% at 50% 88%, rgba(0,0,0,0.94) 20%, rgba(0,0,0,0.6) 55%, transparent 78%)",
        }}
      />

      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center gap-7 pb-[9vh]">
        <div className="intro-mark flex flex-col items-center gap-3">
          <Wordmark className="text-[18px]" />
          <span className="mono-label text-[#8a8f98]">
            PocketQube mission · K J Somaiya
          </span>
        </div>

        <div className="intro-cue translate-y-3 opacity-0">
          <button
            type="button"
            className="intro-enter group flex cursor-pointer flex-col items-center gap-3 rounded-[12px] px-6 py-3 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[#3d6bff]/70"
          >
            <span className="mono-label text-white transition-all duration-500 group-hover:tracking-[0.3em]">
              {typeof window !== "undefined" && window.innerWidth < 768
                ? "Swipe to begin"
                : "Scroll to begin"}
            </span>
            <span className="relative block h-9 w-px overflow-hidden bg-white/20">
              <span className="absolute inset-x-0 top-0 block h-3 animate-[introCue_1.8s_ease-in-out_infinite] bg-[#3d6bff]" />
            </span>
          </button>
        </div>
      </div>
    </div>
  )
}
