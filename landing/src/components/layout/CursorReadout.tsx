/**
 * A tiny mono readout that trails the cursor.
 *
 * Over the hero globe it prints the real latitude/longitude under the pointer
 * (raycast against the globe, published by HeroScene on window.__ssGlobeHit).
 * Everywhere else it prints normalised viewport coordinates.
 *
 * Hidden entirely on touch devices.
 */
import { useEffect, useRef, useState } from "react"

import { isTouchDevice } from "@/lib/gsap"

function fmt(n: number, d = 3) {
  return n.toFixed(d).padStart(d + 3, " ")
}

export function CursorReadout() {
  const el = useRef<HTMLDivElement>(null)
  const label = useRef<HTMLSpanElement>(null)
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    if (isTouchDevice() || window.innerWidth < 768) return
    setEnabled(true)
  }, [])

  useEffect(() => {
    if (!enabled) return

    const pos = { x: 0, y: 0 }
    const shown = { x: 0, y: 0 }
    let raf = 0
    let visible = false

    const onMove = (e: PointerEvent) => {
      pos.x = e.clientX
      pos.y = e.clientY
      if (!visible) {
        visible = true
        if (el.current) el.current.style.opacity = "1"
      }
    }
    const onLeave = () => {
      visible = false
      if (el.current) el.current.style.opacity = "0"
    }

    const tick = () => {
      shown.x += (pos.x - shown.x) * 0.22
      shown.y += (pos.y - shown.y) * 0.22
      if (el.current) {
        el.current.style.transform = `translate3d(${shown.x + 18}px, ${shown.y + 16}px, 0)`
      }
      if (label.current) {
        const hit = window.__ssGlobeHit
        if (hit) {
          const ns = hit.lat >= 0 ? "N" : "S"
          const ew = hit.lng >= 0 ? "E" : "W"
          label.current.textContent =
            `${Math.abs(hit.lat).toFixed(2)}°${ns}  ${Math.abs(hit.lng).toFixed(2)}°${ew}`
          label.current.dataset.mode = "geo"
        } else {
          const nx = pos.x / window.innerWidth
          const ny = pos.y / window.innerHeight
          label.current.textContent = `x ${fmt(nx)}  y ${fmt(ny)}`
          label.current.dataset.mode = "xy"
        }
      }
      raf = requestAnimationFrame(tick)
    }

    window.addEventListener("pointermove", onMove, { passive: true })
    document.addEventListener("pointerleave", onLeave)
    raf = requestAnimationFrame(tick)

    return () => {
      window.removeEventListener("pointermove", onMove)
      document.removeEventListener("pointerleave", onLeave)
      cancelAnimationFrame(raf)
    }
  }, [enabled])

  if (!enabled) return null

  return (
    <div
      ref={el}
      aria-hidden="true"
      className="pointer-events-none fixed left-0 top-0 z-[60] opacity-0 transition-opacity duration-300 will-change-transform"
    >
      <span
        ref={label}
        data-mode="xy"
        className="mono-label whitespace-pre rounded-[6px] border border-white/[0.12] bg-black/70 px-2 py-1 text-[10px] tabular-nums backdrop-blur-md data-[mode=geo]:border-[#3d6bff]/50 data-[mode=geo]:text-[#7f9dff] data-[mode=xy]:text-[#8a8f98]"
      >
        x 0.000 y 0.000
      </span>
    </div>
  )
}
