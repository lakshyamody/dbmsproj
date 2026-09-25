/**
 * Shared scroll progress for the pinned hero.
 *
 * ScrollTrigger writes a plain number into a ref; the R3F components read that
 * ref inside useFrame. Nothing here goes through React state, so scrubbing the
 * hero never triggers a re-render — which is what keeps it at 60fps.
 */
import { createContext, useContext } from "react"

export interface SceneProgress {
  /** 0 -> 1 across the whole pinned hero. */
  current: number
  /** True while the hero is on screen; scenes pause rendering when false. */
  visible: boolean
}

export const SceneProgressContext = createContext<{ value: SceneProgress }>({
  value: { current: 0, visible: true },
})

export function useSceneProgress() {
  return useContext(SceneProgressContext)
}

/** Smooth 0..1 ramp between two thresholds. */
export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0 || 1e-6)))
  return t * t * (3 - 2 * t)
}

/** Linear 0..1 ramp, clamped. */
export function ramp(edge0: number, edge1: number, x: number): number {
  return Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0 || 1e-6)))
}

/**
 * Scene windows across the hero's 0..1 progress. Each scene fades in over its
 * first band and out over its last, so neighbours crossfade rather than cut.
 */
export const SCENES = {
  constellation: { in: [-0.05, 0.0], out: [0.2, 0.3] },
  dive: { in: [0.2, 0.3], out: [0.46, 0.55] },
  deployment: { in: [0.46, 0.55], out: [0.7, 0.78] },
  link: { in: [0.7, 0.78], out: [0.99, 1.0] },
} as const

/** Opacity of a scene at progress p, given its window. */
export function sceneOpacity(
  window: { in: readonly [number, number] | number[]; out: readonly [number, number] | number[] },
  p: number
): number {
  const fadeIn = smoothstep(window.in[0], window.in[1], p)
  const fadeOut = 1 - smoothstep(window.out[0], window.out[1], p)
  return Math.min(fadeIn, fadeOut)
}
