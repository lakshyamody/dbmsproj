/**
 * Spiral animation — a canvas particle field that draws a spiral arm and then
 * throws its stars outward past the camera.
 *
 * Adapted from a community component. Changes made for this codebase:
 *
 *  - Rewritten for the project's TypeScript config: no parameter properties
 *    (`erasableSyntaxOnly`), no unused private fields (`noUnusedLocals`), and
 *    no bracket access of private members (`strict` is on by default in TS 6).
 *  - GSAP comes from `@/lib/gsap` so plugin registration can't race.
 *  - Determinism now uses a seeded PRNG instead of monkey-patching the global
 *    `Math.random`.
 *  - Fixed: stars were created twice (10k instead of 5k).
 *  - Fixed: `showProjectedDot` set `ctx.lineWidth` and then `fill()`ed an arc of
 *    fixed radius 0.5, so the entire per-star size calculation was discarded.
 *    The radius now actually comes from the projected size.
 *  - Fixed: the canvas used a square backing store with non-square CSS
 *    dimensions, which stretched the whole render. Now correct for DPR and
 *    aspect, with a uniform scale.
 *  - Hot-path allocations removed (scratch vectors, scalar args) so 5k stars
 *    hold 60fps.
 */
import { useEffect, useRef } from "react"

import { gsap } from "@/lib/gsap"

/** Small deterministic PRNG, so the field looks identical on every load. */
function makeRandom(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

interface Vec2 {
  x: number
  y: number
}

const CHANGE_EVENT_TIME = 0.32
const CAMERA_Z = -400
const CAMERA_TRAVEL = 3400
const START_DOT_Y = 28
const VIEW_ZOOM = 100
const TRAIL_LENGTH = 300
/** How much of the spiral the drawn arm spans behind the head. */
const TRAIL_SPAN = 0.34
const SPIRAL_TURNS = 6
const SPIRAL_RADIUS = 170

/** Design-space width the scene is authored against. */
const BASE_SIZE = 860

function ease(p: number, g: number): number {
  return p < 0.5 ? 0.5 * Math.pow(2 * p, g) : 1 - 0.5 * Math.pow(2 * (1 - p), g)
}

function easeOutElastic(x: number): number {
  if (x <= 0) return 0
  if (x >= 1) return 1
  const c4 = (2 * Math.PI) / 4.5
  return Math.pow(2, -8 * x) * Math.sin((x * 8 - 0.75) * c4) + 1
}

function mapRange(v: number, a1: number, b1: number, a2: number, b2: number): number {
  return a2 + (b2 - a2) * ((v - a1) / (b1 - a1))
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(Math.max(v, lo), hi)
}

function lerp(a: number, b: number, t: number): number {
  return a * (1 - t) + b * t
}

/** Point on the spiral at normalised progress p, written into `out`. */
function spiralPath(p: number, out: Vec2): Vec2 {
  const q = ease(clamp(1.2 * p, 0, 1), 1.8)
  const theta = 2 * Math.PI * SPIRAL_TURNS * Math.sqrt(q)
  const r = SPIRAL_RADIUS * Math.sqrt(q)
  out.x = r * Math.cos(theta)
  out.y = r * Math.sin(theta) + START_DOT_Y
  return out
}

// ---------------------------------------------------------------------------

class Star {
  private dx: number
  private dy: number
  private spiralLocation: number
  private weight: number
  private z: number
  private angle: number
  private distance: number
  private spin: number
  private expansion: number
  private finalScale: number

  constructor(rnd: () => number) {
    this.angle = rnd() * Math.PI * 2
    this.distance = 30 * rnd() + 15
    this.spin = rnd() > 0.5 ? 1 : -1
    this.expansion = 1.2 + rnd() * 0.8
    this.finalScale = 0.7 + rnd() * 0.6

    this.dx = this.distance * Math.cos(this.angle)
    this.dy = this.distance * Math.sin(this.angle)

    this.spiralLocation = (1 - Math.pow(1 - rnd(), 3)) / 1.3
    const z0 = 0.5 * CAMERA_Z + rnd() * (CAMERA_TRAVEL + CAMERA_Z - 0.5 * CAMERA_Z)
    this.z = lerp(z0, CAMERA_TRAVEL / 2, 0.3 * this.spiralLocation)
    this.weight = Math.pow(rnd(), 2)
  }

  render(p: number, ctrl: AnimationController, scratch: Vec2): void {
    const q = p - this.spiralLocation
    if (q <= 0) return

    const sp = spiralPath(this.spiralLocation, scratch)
    const spx = sp.x
    const spy = sp.y

    const t = clamp(2.6 * q, 0, 1)

    let screenX: number
    let screenY: number

    if (t < 0.3) {
      // Leaves the arm in a straight line.
      const k = Math.pow(t, 2) / 0.3
      screenX = lerp(spx, spx + this.dx * 0.3, k)
      screenY = lerp(spy, spy + this.dy * 0.3, k)
    } else if (t < 0.7) {
      // Curves away from the arm.
      const m = (t - 0.3) / 0.4
      const curve = Math.sin(m * Math.PI) * this.spin * 1.5
      const baseX = spx + this.dx * 0.3
      const baseY = spy + this.dy * 0.3
      const targetX = spx + this.dx * 0.7
      const targetY = spy + this.dy * 0.7
      screenX = lerp(baseX, targetX, m) + -this.dy * 0.4 * curve * m
      screenY = lerp(baseY, targetY, m) + this.dx * 0.4 * curve * m
    } else {
      // Spirals outward with an elastic settle.
      const f = easeOutElastic((t - 0.7) / 0.3)
      const baseX = spx + this.dx * 0.7
      const baseY = spy + this.dy * 0.7
      const dist = this.distance * this.expansion * 1.5
      const a = this.angle + 1.2 * this.spin * f * Math.PI
      screenX = lerp(baseX, spx + dist * Math.cos(a), f)
      screenY = lerp(baseY, spy + dist * Math.sin(a), f)
    }

    // Screen position back out into the 3D field.
    const depth = this.z - CAMERA_Z
    const vx = (depth * screenX) / VIEW_ZOOM
    const vy = (depth * screenY) / VIEW_ZOOM

    let sizeMul: number
    if (t < 0.6) {
      sizeMul = 1 + t * 0.2
    } else {
      const k = (t - 0.6) / 0.4
      sizeMul = 1.2 * (1 - k) + this.finalScale * k
    }

    ctrl.showProjectedDot(vx, vy, this.z, 8.5 * this.weight * sizeMul)
  }
}

// ---------------------------------------------------------------------------

class AnimationController {
  private ctx: CanvasRenderingContext2D
  private tl: gsap.core.Timeline
  private stars: Star[] = []
  private time = 0
  private cssW = 0
  private cssH = 0
  private dpr = 1
  private scale = 1
  private scratch: Vec2 = { x: 0, y: 0 }
  private trailScratch: Vec2 = { x: 0, y: 0 }

  constructor(ctx: CanvasRenderingContext2D, starCount: number, duration: number) {
    this.ctx = ctx

    const rnd = makeRandom(20260923)
    for (let i = 0; i < starCount; i++) this.stars.push(new Star(rnd))

    this.tl = gsap.timeline({ repeat: -1 }).to(this, {
      time: 1,
      duration,
      ease: "none",
      onUpdate: () => this.render(),
    })
  }

  /** Called on mount and on every resize. */
  resize(cssW: number, cssH: number, dpr: number): void {
    this.cssW = cssW
    this.cssH = cssH
    this.dpr = dpr
    this.scale = Math.max(cssW, cssH) / BASE_SIZE
  }

  /**
   * Project a point in the field to the screen and draw it.
   * Sub-pixel dots use fillRect, which is materially cheaper than arc() and
   * indistinguishable at that size.
   */
  showProjectedDot(x: number, y: number, z: number, sizeFactor: number): void {
    const t2 = clamp(mapRange(this.time, CHANGE_EVENT_TIME, 1, 0, 1), 0, 1)
    const camZ = CAMERA_Z + ease(Math.pow(t2, 1.2), 1.8) * CAMERA_TRAVEL
    if (z <= camZ) return

    const depth = z - camZ
    const px = (VIEW_ZOOM * x) / depth
    const py = (VIEW_ZOOM * y) / depth
    const r = (400 * sizeFactor) / depth / 2
    if (r <= 0.05) return

    const ctx = this.ctx
    if (r < 1.5) {
      const d = r * 2
      ctx.fillRect(px - r, py - r, d, d)
    } else {
      ctx.beginPath()
      ctx.arc(px, py, r, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  private drawTrail(t1: number): void {
    const ctx = this.ctx
    ctx.fillStyle = "#ffffff"

    // The arm is drawn as a long tapering ribbon behind the head, so the
    // spiral reads as a shape rather than as a short comet.
    for (let i = 0; i < TRAIL_LENGTH; i++) {
      const k = i / TRAIL_LENGTH
      const p = t1 - k * TRAIL_SPAN
      if (p <= 0) break

      const taper = Math.pow(1 - k, 1.6)
      const sw = (1.6 * (1 - t1 * 0.45) + 3 * Math.sin(Math.PI * t1)) * (0.18 + 1.05 * taper)
      if (sw <= 0.04) continue

      const pos = spiralPath(p, this.trailScratch)
      ctx.beginPath()
      ctx.arc(pos.x, pos.y, sw / 2, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  private drawStartDot(): void {
    if (this.time <= CHANGE_EVENT_TIME) return
    const dy = (CAMERA_Z * START_DOT_Y) / VIEW_ZOOM
    this.showProjectedDot(0, dy, CAMERA_TRAVEL, 2.5)
  }

  render(): void {
    const ctx = this.ctx
    if (!this.cssW || !this.cssH) return

    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0)
    ctx.fillStyle = "#000000"
    ctx.fillRect(0, 0, this.cssW, this.cssH)

    ctx.save()
    ctx.translate(this.cssW / 2, this.cssH / 2)
    ctx.scale(this.scale, this.scale)

    const t1 = clamp(mapRange(this.time, 0, CHANGE_EVENT_TIME + 0.25, 0, 1), 0, 1)
    const t2 = clamp(mapRange(this.time, CHANGE_EVENT_TIME, 1, 0, 1), 0, 1)

    ctx.rotate(-Math.PI * ease(t2, 2.7))

    this.drawTrail(t1)

    ctx.fillStyle = "#ffffff"
    for (const star of this.stars) star.render(t1, this, this.scratch)

    this.drawStartDot()

    ctx.restore()
  }

  destroy(): void {
    this.tl.kill()
    this.stars.length = 0
  }
}

// ---------------------------------------------------------------------------

export interface SpiralAnimationProps {
  /** Number of particles. Defaults to 5000, or 2000 on small viewports. */
  starCount?: number
  /** Seconds for one full loop. */
  duration?: number
  className?: string
}

export function SpiralAnimation({
  starCount,
  duration = 10,
  className,
}: SpiralAnimationProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const count = starCount ?? (window.innerWidth < 768 ? 2000 : 5000)
    const controller = new AnimationController(ctx, count, duration)

    const resize = () => {
      const w = window.innerWidth
      const h = window.innerHeight
      const dpr = Math.min(2, window.devicePixelRatio || 1)

      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`

      controller.resize(w, h, dpr)
      controller.render()
    }

    resize()
    window.addEventListener("resize", resize)

    return () => {
      window.removeEventListener("resize", resize)
      controller.destroy()
    }
  }, [starCount, duration])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={className ?? "block h-full w-full"}
    />
  )
}
