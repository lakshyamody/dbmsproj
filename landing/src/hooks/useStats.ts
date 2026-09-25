/**
 * Loads data/stats.json, produced by scripts/export_stats.py.
 *
 * The page must never depend on it: if the fetch fails, or the file was never
 * generated, we fall back to a built-in snapshot with the identical shape so
 * every counter and label still renders.
 */
import { useEffect, useState } from "react"

export interface Satellite {
  cube_id: string
  pod_id: string | null
  mech_type: string | null
  confirm_status: string | null
  launch_date: string | null
  power_state: string | null
  sys_init: string | null
  router_id: string | null
  link_score: number
  link_band: "good" | "fair" | "poor"
  chain_status: string | null
  health_flag: string | null
  packet_count: number
  unsent_count: number
  battery_latest: number | null
  battery_avg: number | null
  battery_min: number | null
  battery_24h: number[]
  battery_24h_ago: number | null
  temp_max: number | null
  temp_min: number | null
  last_packet_at: string | null
  next_pass: string | null
  next_pass_id: number | null
  deployed: boolean
}

export interface Payload {
  payload_type: string
  priority: number
  description: string
  packet_count: number
  unsent_count: number
  total_bytes: number
}

export interface GroundPass {
  pass_id: number
  cube_id: string
  start_time: string
  end_time: string
  max_link_score: number
  duration_s: number
}

export interface Station {
  id: string
  name: string
  country: string
  lat: number
  lng: number
  primary: boolean
}

export interface Totals {
  satellites: number
  deployed_satellites: number
  pods: number
  packets: number
  unsent_packets: number
  passes: number
  payload_modes: number
  total_bytes: number
  ground_stations: number
  /** Real satellites tracked from live CelesTrak element sets. */
  tracked_objects: number
  /** Real pass windows computed by SGP4 over the station network. */
  tracked_passes: number
}

/** A real satellite in orbit now -- not part of the proposed mission. */
export interface TrackedObject {
  norad_id: number
  object_name: string
  payload_modes: string | null
  inclination_deg: number
  period_min: number
  tle_age_days: number
  tle_status: "FRESH" | "AGEING" | "STALE"
  next_aos: string | null
  next_link: number | null
}

export interface Stats {
  source: "database" | "mock" | "fallback"
  generated_at: string
  satellites: Satellite[]
  payloads: Payload[]
  passes: GroundPass[]
  stations: Station[]
  tracked: TrackedObject[]
  totals: Totals
}

/** Built-in snapshot: last resort so the UI never renders empty. */
export const FALLBACK_STATS: Stats = {
  source: "fallback",
  generated_at: new Date().toISOString(),
  satellites: [
    {
      cube_id: "CUBE01", pod_id: "POD01", mech_type: "Spring-Loaded Rail",
      confirm_status: "Confirmed", launch_date: "2026-01-14", power_state: "Nominal",
      sys_init: "Complete", router_id: "RTR01", link_score: 85, link_band: "good",
      chain_status: "OPERATIONAL", health_flag: "HEALTHY", packet_count: 1666,
      unsent_count: 341, battery_latest: 7.8, battery_avg: 7.93, battery_min: 7.61,
      battery_24h: [7.95, 7.92, 7.9, 7.88, 7.87, 7.86, 7.84, 7.83, 7.82, 7.81, 7.8, 7.8],
      battery_24h_ago: 7.95, temp_max: 38.99, temp_min: 20, last_packet_at: null,
      next_pass: null, next_pass_id: null, deployed: true,
    },
    {
      cube_id: "CUBE02", pod_id: "POD02", mech_type: "Spring-Loaded Rail",
      confirm_status: "Confirmed", launch_date: "2026-01-14", power_state: "Low",
      sys_init: "Complete", router_id: "RTR02", link_score: 70, link_band: "good",
      chain_status: "OPERATIONAL", health_flag: "WARNING", packet_count: 1666,
      unsent_count: 336, battery_latest: 6.9, battery_avg: 7.23, battery_min: 6.71,
      battery_24h: [7.2, 7.15, 7.11, 7.08, 7.04, 7.01, 6.99, 6.97, 6.95, 6.93, 6.91, 6.9],
      battery_24h_ago: 7.2, temp_max: 41, temp_min: 24, last_packet_at: null,
      next_pass: null, next_pass_id: null, deployed: true,
    },
    {
      cube_id: "CUBE03", pod_id: "POD03", mech_type: "Pusher Plate",
      confirm_status: "Confirmed", launch_date: "2026-02-02", power_state: "Nominal",
      sys_init: "Complete", router_id: "RTR03", link_score: 30, link_band: "poor",
      chain_status: "OPERATIONAL", health_flag: "THERMAL WATCH", packet_count: 1666,
      unsent_count: 327, battery_latest: 7.6, battery_avg: 7.78, battery_min: 7.48,
      battery_24h: [7.8, 7.78, 7.76, 7.74, 7.72, 7.7, 7.68, 7.66, 7.64, 7.62, 7.61, 7.6],
      battery_24h_ago: 7.8, temp_max: 45, temp_min: 22, last_packet_at: null,
      next_pass: null, next_pass_id: null, deployed: true,
    },
  ],
  payloads: [
    { payload_type: "TT&C", priority: 1, description: "Telemetry, tracking & command housekeeping", packet_count: 2490, unsent_count: 501, total_bytes: 401698 },
    { payload_type: "SSTV", priority: 2, description: "Slow-scan TV imagery", packet_count: 737, unsent_count: 151, total_bytes: 33888052 },
    { payload_type: "M17", priority: 3, description: "M17 digital voice / data", packet_count: 1014, unsent_count: 201, total_bytes: 2599610 },
    { payload_type: "Codec2", priority: 4, description: "Codec2 low-bitrate voice", packet_count: 757, unsent_count: 151, total_bytes: 1943233 },
  ],
  passes: [],
  stations: [
    { id: "KJSSE", name: "KJSSE Mumbai", country: "India", lat: 19.07, lng: 72.9, primary: true },
    { id: "HEL", name: "Helsinki", country: "Finland", lat: 60.17, lng: 24.94, primary: true },
    { id: "SVAL", name: "Svalbard", country: "Norway", lat: 78.22, lng: 15.65, primary: false },
    { id: "BLR", name: "Bengaluru", country: "India", lat: 12.97, lng: 77.59, primary: false },
    { id: "SGP", name: "Singapore", country: "Singapore", lat: 1.35, lng: 103.82, primary: false },
    { id: "SNT", name: "Santiago", country: "Chile", lat: -33.45, lng: -70.67, primary: false },
  ],
  // Empty, not faked: a made-up element set would propagate to a real-looking
  // position that is simply wrong.
  tracked: [],
  totals: {
    satellites: 4, deployed_satellites: 3, pods: 4, packets: 4998,
    unsent_packets: 1004, passes: 9, payload_modes: 4,
    total_bytes: 38832593, ground_stations: 6,
    tracked_objects: 0, tracked_passes: 0,
  },
}

export function useStats(): { stats: Stats; loading: boolean } {
  const [stats, setStats] = useState<Stats>(FALLBACK_STATS)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    const url = `${import.meta.env.BASE_URL}data/stats.json`

    fetch(url, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((json: Stats) => {
        if (!alive) return
        // Guard against a truncated or hand-edited file.
        if (json && Array.isArray(json.satellites) && json.totals) setStats(json)
      })
      .catch(() => {
        /* keep the fallback snapshot */
      })
      .finally(() => alive && setLoading(false))

    return () => {
      alive = false
    }
  }, [])

  return { stats, loading }
}

/** Satellites that actually fly — CUBE04 is still in its pod. */
export function deployedSats(stats: Stats): Satellite[] {
  return stats.satellites.filter((s) => s.deployed && s.battery_latest !== null)
}
