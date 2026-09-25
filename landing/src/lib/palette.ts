/** Design tokens mirrored in TS so canvas/WebGL code uses the same values. */
export const PALETTE = {
  black: "#000000",
  white: "#ffffff",
  accent: "#3d6bff",
  accentDim: "#1b2f7a",
  muted: "#8a8f98",
  line: "rgba(255,255,255,0.12)",
  good: "#3ddc97",
  fair: "#ffb547",
  poor: "#ff5c7a",
} as const

/** Link-quality band -> colour. Matches the router's own thresholds. */
export function linkColor(score: number): string {
  if (score >= 70) return PALETTE.good
  if (score >= 40) return PALETTE.fair
  return PALETTE.poor
}

export function linkBandLabel(score: number): string {
  if (score >= 70) return "GOOD"
  if (score >= 40) return "FAIR"
  return "POOR"
}

/** Payload display metadata, priority order matches payload_priority. */
export const PAYLOAD_META: Record<
  string,
  { label: string; blurb: string; priority: number }
> = {
  "TT&C": {
    label: "TT&C",
    blurb:
      "Telemetry, Tracking & Command — the spacecraft's health and status. " +
      "Always highest priority; never dropped, never deferred.",
    priority: 1,
  },
  SSTV: {
    label: "SSTV",
    blurb:
      "Slow-scan TV image transmission. Bandwidth-heavy frames, and the " +
      "first thing a thin power budget gives up.",
    priority: 2,
  },
  M17: {
    label: "M17",
    blurb:
      "M17 digital voice and data transmission, carried whenever the link " +
      "will hold it.",
    priority: 3,
  },
  Codec2: {
    label: "Codec2",
    blurb:
      "Codec2 low-bitrate digital voice. Cheap to send, and last in the " +
      "priority queue.",
    priority: 4,
  },
}
