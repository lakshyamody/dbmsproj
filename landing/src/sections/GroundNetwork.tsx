/**
 * [ GROUND NETWORK ] — a halftone dot map drawn on canvas from the same land
 * mask the 3D globe uses.
 *
 * Land reads as a grey dot grid. The stations, and the dots clustered around
 * them, light up blue one after another, and thin arcs draw between them.
 */
import { useEffect, useRef, useState } from "react"

import { SectionLabel } from "@/components/brand/Brand"
import { loadLandMask, type LandMask } from "@/lib/landmask"
import { prefersReducedMotion } from "@/lib/gsap"
import type { Stats } from "@/hooks/useStats"

const STEP = 7 // px between dot centres
const DOT = 1.55
const CLUSTER_KM = 1500

/** Great-circle distance in km. */
function haversine(a: [number, number], b: [number, number]) {
  const R = 6371
  const dLat = ((b[0] - a[0]) * Math.PI) / 180
  const dLng = ((b[1] - a[1]) * Math.PI) / 180
  const la1 = (a[0] * Math.PI) / 180
  const la2 = (b[0] * Math.PI) / 180
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

export function GroundNetwork({ stats }: { stats: Stats }) {
  const wrap = useRef<HTMLDivElement>(null)
  const canvas = useRef<HTMLCanvasElement>(null)
  const [mask, setMask] = useState<LandMask | null>(null)
  const [live, setLive] = useState(false)

  useEffect(() => {
    loadLandMask().then(setMask)
  }, [])

  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const io = new IntersectionObserver(
      ([e]) => e.isIntersecting && setLive(true),
      { rootMargin: "-10% 0px" }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    const cv = canvas.current
    const el = wrap.current
    if (!cv || !el || !mask) return

    const reduced = prefersReducedMotion()
    const ctx = cv.getContext("2d")!
    let raf = 0
    let start = 0

    const stations = stats.stations

    const draw = (now: number) => {
      if (!start) start = now
      const t = reduced ? 9999 : (now - start) / 1000

      const dpr = Math.min(2, window.devicePixelRatio || 1)
      const w = el.clientWidth
      const h = Math.round(w / 2) // equirectangular 2:1
      if (cv.width !== w * dpr || cv.height !== h * dpr) {
        cv.width = w * dpr
        cv.height = h * dpr
        cv.style.width = `${w}px`
        cv.style.height = `${h}px`
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)

      const cols = Math.floor(w / STEP)
      const rows = Math.floor(h / STEP)

      // Station reveal order, one every 0.35s.
      const revealed = stations.map((_, i) => (t - 0.7 - i * 0.35) / 0.9)

      for (let ry = 0; ry < rows; ry++) {
        for (let rx = 0; rx < cols; rx++) {
          const px = rx * STEP + STEP / 2
          const py = ry * STEP + STEP / 2
          const lng = (px / w) * 360 - 180
          const lat = 90 - (py / h) * 180
          if (!mask.isLandAt(lat, lng)) continue

          // Is this dot inside a station's cluster?
          let glow = 0
          for (let s = 0; s < stations.length; s++) {
            const st = stations[s]
            const d = haversine([lat, lng], [st.lat, st.lng])
            if (d < CLUSTER_KM) {
              const falloff = 1 - d / CLUSTER_KM
              const reveal = Math.max(0, Math.min(1, revealed[s]))
              glow = Math.max(glow, falloff * reveal)
            }
          }

          if (glow > 0.02) {
            const a = 0.2 + glow * 0.8
            ctx.fillStyle = `rgba(61,107,255,${a})`
            ctx.beginPath()
            ctx.arc(px, py, DOT + glow * 1.15, 0, Math.PI * 2)
            ctx.fill()
          } else {
            ctx.fillStyle = "rgba(255,255,255,0.16)"
            ctx.beginPath()
            ctx.arc(px, py, DOT, 0, Math.PI * 2)
            ctx.fill()
          }
        }
      }

      // Arcs between the primary stations and everything else.
      const toXY = (lat: number, lng: number): [number, number] => [
        ((lng + 180) / 360) * w,
        ((90 - lat) / 180) * h,
      ]
      const primaries = stations.filter((s) => s.primary)
      let arcIndex = 0
      for (const a of primaries) {
        for (const b of stations) {
          if (a.id === b.id) continue
          const p = Math.max(0, Math.min(1, (t - 1.6 - arcIndex * 0.18) / 1.1))
          arcIndex++
          if (p <= 0) continue

          const [x1, y1] = toXY(a.lat, a.lng)
          const [x2, y2] = toXY(b.lat, b.lng)
          const mx = (x1 + x2) / 2
          const my = (y1 + y2) / 2 - Math.abs(x2 - x1) * 0.18 - 14

          ctx.strokeStyle = `rgba(61,107,255,${0.34 * p})`
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.moveTo(x1, y1)
          // Partial quadratic: sample up to p.
          const steps = 40
          for (let i = 1; i <= steps * p; i++) {
            const u = i / steps
            const xx = (1 - u) ** 2 * x1 + 2 * (1 - u) * u * mx + u * u * x2
            const yy = (1 - u) ** 2 * y1 + 2 * (1 - u) * u * my + u * u * y2
            ctx.lineTo(xx, yy)
          }
          ctx.stroke()
        }
      }

      // Station markers + labels.
      stations.forEach((s, i) => {
        const r = Math.max(0, Math.min(1, revealed[i]))
        if (r <= 0) return
        const [x, y] = toXY(s.lat, s.lng)

        if (!reduced) {
          const pulse = (t * 0.8 + i * 0.3) % 1
          ctx.strokeStyle = `rgba(61,107,255,${(1 - pulse) * 0.5 * r})`
          ctx.lineWidth = 1
          ctx.beginPath()
          ctx.arc(x, y, 6 + pulse * 20, 0, Math.PI * 2)
          ctx.stroke()
        }

        ctx.fillStyle = `rgba(255,255,255,${r})`
        ctx.beginPath()
        ctx.arc(x, y, s.primary ? 3.6 : 2.6, 0, Math.PI * 2)
        ctx.fill()

        ctx.fillStyle = `rgba(${s.primary ? "255,255,255" : "138,143,152"},${r})`
        ctx.font = `${s.primary ? 11 : 10}px "JetBrains Mono", monospace`
        ctx.textAlign = x > w * 0.82 ? "right" : "left"
        const dx = x > w * 0.82 ? -10 : 10
        ctx.fillText(s.name.toUpperCase(), x + dx, y + 4)
      })

      if (!reduced) raf = requestAnimationFrame(draw)
    }

    if (live) raf = requestAnimationFrame(draw)
    const onResize = () => {
      start = 0
      if (!live) return
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(draw)
    }
    window.addEventListener("resize", onResize)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("resize", onResize)
    }
  }, [mask, live, stats.stations])

  return (
    <section
      id="network"
      data-glitch
      className="border-t border-white/[0.12] py-24 md:py-32"
    >
      <div className="shell">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <SectionLabel>Ground network</SectionLabel>
            <h2
              className="mt-8 max-w-[20ch] font-semibold leading-[1.06] tracking-[-0.03em]"
              style={{ fontSize: "clamp(34px, 5vw, 72px)" }}
            >
              The spacecraft is only ever talking to one of these.
            </h2>
          </div>
          <p className="max-w-[40ch] text-sm leading-[1.8] text-[#8a8f98]">
            Mumbai is the home station; Helsinki is our collaborating site with
            ReOrbit. Between them the fleet gets a handful of usable windows a
            day, and the router has to spend each one well.
          </p>
        </div>

        <div ref={wrap} className="mt-16">
          <canvas ref={canvas} className="w-full" aria-hidden="true" />
        </div>

        <ul className="mt-12 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          {stats.stations.map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between border-t border-white/[0.12] pt-4"
            >
              <span className="flex items-center gap-3">
                <span
                  className={`size-1.5 rounded-full ${
                    s.primary ? "bg-[#3d6bff]" : "bg-white/30"
                  }`}
                />
                <span className="text-sm text-white/90">{s.name}</span>
              </span>
              <span className="mono-label text-[#8a8f98]">
                {s.lat.toFixed(2)}, {s.lng.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
