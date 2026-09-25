/**
 * Single place where GSAP plugins are registered. Import from here, never from
 * "gsap" directly, so registration can never race a component that needs it.
 */
import { gsap } from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { SplitText } from "gsap/SplitText"
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin"
import { MotionPathPlugin } from "gsap/MotionPathPlugin"
import { useGSAP } from "@gsap/react"

gsap.registerPlugin(
  ScrollTrigger,
  SplitText,
  DrawSVGPlugin,
  MotionPathPlugin,
  useGSAP
)

// Snappier defaults than GSAP's stock ease.
gsap.defaults({ ease: "power3.out", duration: 0.8 })

/** True when the visitor asked the OS for less motion. */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

/** Phone-sized viewport: fewer points, shorter pins, no cursor readout. */
export function isMobileViewport(): boolean {
  if (typeof window === "undefined") return false
  return window.innerWidth < 768
}

/** Coarse pointer — hide anything that depends on a hovering cursor. */
export function isTouchDevice(): boolean {
  if (typeof window === "undefined") return false
  return window.matchMedia("(hover: none), (pointer: coarse)").matches
}

export { gsap, ScrollTrigger, SplitText, DrawSVGPlugin, MotionPathPlugin, useGSAP }
