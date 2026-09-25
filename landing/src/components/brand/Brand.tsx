/**
 * Brand primitives: the wordmark with its orbit-ring glyph, the [ SECTION ]
 * label, and the small mono readout used for numbers.
 *
 * All artwork here is original to this project.
 */
import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * The orbit-ring glyph that stands in for the "a" of "Sat": a filled body with
 * a tilted ellipse swung around it, sized to sit on the text baseline.
 */
export function OrbitGlyph({
  className,
  strokeWidth = 1.6,
}: {
  className?: string
  strokeWidth?: number
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn("inline-block", className)}
    >
      <circle cx="12" cy="12" r="4.1" fill="currentColor" />
      <ellipse
        cx="12"
        cy="12"
        rx="10.6"
        ry="5.1"
        transform="rotate(-27 12 12)"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        opacity="0.92"
      />
      {/* the satellite riding the ring */}
      <circle cx="21.2" cy="8.1" r="1.5" fill="#3d6bff" />
    </svg>
  )
}

/** "SomaiyaSat" with the second "a" of Sat replaced by the orbit glyph. */
export function Wordmark({
  className,
  glyphClassName,
}: {
  className?: string
  glyphClassName?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex select-none items-baseline font-semibold tracking-[-0.02em]",
        className
      )}
    >
      <span>SomaiyaS</span>
      <OrbitGlyph
        className={cn("mx-[0.02em] size-[0.78em] translate-y-[0.03em]", glyphClassName)}
      />
      <span>t</span>
      <span className="sr-only">SomaiyaSat</span>
    </span>
  )
}

/** Small mono label in square brackets, e.g. [ THE MISSION ]. */
export function SectionLabel({
  children,
  className,
  accent = false,
}: {
  children: React.ReactNode
  className?: string
  accent?: boolean
}) {
  return (
    <span
      className={cn(
        "mono-label inline-flex items-center gap-[0.6em]",
        accent ? "text-[#3d6bff]" : "text-[#8a8f98]",
        className
      )}
    >
      <span aria-hidden="true">[</span>
      <span>{children}</span>
      <span aria-hidden="true">]</span>
    </span>
  )
}

/** A number with an optional unit, set in mono so digits line up. */
export function MonoReadout({
  value,
  unit,
  label,
  className,
  tone = "default",
}: {
  value: React.ReactNode
  unit?: string
  label?: string
  className?: string
  tone?: "default" | "accent" | "good" | "fair" | "poor"
}) {
  const toneClass = {
    default: "text-white",
    accent: "text-[#3d6bff]",
    good: "text-[#3ddc97]",
    fair: "text-[#ffb547]",
    poor: "text-[#ff5c7a]",
  }[tone]

  return (
    <span className={cn("inline-flex flex-col gap-1", className)}>
      {label && (
        <span className="mono-label text-[#8a8f98]">{label}</span>
      )}
      <span className={cn("font-mono tabular-nums", toneClass)}>
        {value}
        {unit && (
          <span className="ml-1 text-[0.62em] text-[#8a8f98]">{unit}</span>
        )}
      </span>
    </span>
  )
}

/** Thin horizontal rule used between rows. */
export function Hairline({ className }: { className?: string }) {
  return <div className={cn("h-px w-full bg-white/[0.12]", className)} />
}
