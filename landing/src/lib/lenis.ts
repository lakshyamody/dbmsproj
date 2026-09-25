/**
 * Lenis smooth scroll, driven by GSAP's ticker and wired into ScrollTrigger so
 * pinned sections and scrubs stay in sync with the eased scroll position.
 */
import Lenis from "lenis"
import { gsap, ScrollTrigger, prefersReducedMotion } from "./gsap"

let lenis: Lenis | null = null

export function initLenis(): Lenis | null {
  if (lenis) return lenis
  // Reduced motion: leave native scrolling alone entirely.
  if (prefersReducedMotion()) return null

  lenis = new Lenis({
    duration: 1.05,
    easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    smoothWheel: true,
    syncTouch: false,
    touchMultiplier: 1.6,
  })

  lenis.on("scroll", ScrollTrigger.update)

  const raf = (time: number) => lenis?.raf(time * 1000)
  gsap.ticker.add(raf)
  gsap.ticker.lagSmoothing(0)

  // Let ScrollTrigger drive Lenis for scrollTo/refresh round-trips.
  ScrollTrigger.scrollerProxy(document.documentElement, {
    scrollTop(value) {
      if (value !== undefined) lenis?.scrollTo(value, { immediate: true })
      return lenis?.scroll ?? window.scrollY
    },
  })

  ;(lenis as unknown as { __rafFn?: (t: number) => void }).__rafFn = raf
  return lenis
}

export function getLenis(): Lenis | null {
  return lenis
}

export function stopScroll() {
  lenis?.stop()
  document.documentElement.classList.add("lenis-stopped")
}

export function startScroll() {
  lenis?.start()
  document.documentElement.classList.remove("lenis-stopped")
}

export function scrollToId(id: string) {
  const el = document.getElementById(id)
  if (!el) return
  if (lenis) lenis.scrollTo(el, { offset: 0, duration: 1.2 })
  else el.scrollIntoView({ behavior: "smooth" })
}

export function destroyLenis() {
  if (!lenis) return
  const raf = (lenis as unknown as { __rafFn?: (t: number) => void }).__rafFn
  if (raf) gsap.ticker.remove(raf)
  lenis.destroy()
  lenis = null
}
