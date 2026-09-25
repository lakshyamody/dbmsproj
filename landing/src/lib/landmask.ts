/**
 * Land/water mask sampling.
 *
 * public/assets/textures/land_mask.png is a 1024x512 equirectangular mask
 * derived from the NASA Blue Marble texture by scripts/prepare_assets.py
 * (white = land, black = water). Both the point-cloud Earth and the halftone
 * world map are generated from it, so they always agree on where land is.
 *
 * The decoded mask is cached: it is fetched once per page load.
 */

export interface LandMask {
  width: number
  height: number
  /** 1 byte per pixel, 255 = land. */
  data: Uint8Array
  /** Row-major lookup in equirectangular space. */
  isLand(x: number, y: number): boolean
  /** Lookup by geographic coordinate. */
  isLandAt(lat: number, lng: number): boolean
}

let cache: Promise<LandMask | null> | null = null

function decode(img: HTMLImageElement): LandMask {
  const w = img.naturalWidth
  const h = img.naturalHeight
  const canvas = document.createElement("canvas")
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!
  ctx.drawImage(img, 0, 0)
  const rgba = ctx.getImageData(0, 0, w, h).data

  const data = new Uint8Array(w * h)
  for (let i = 0, p = 0; i < data.length; i++, p += 4) {
    data[i] = rgba[p] // grayscale: red channel is enough
  }

  return {
    width: w,
    height: h,
    data,
    isLand(x, y) {
      if (x < 0 || y < 0 || x >= w || y >= h) return false
      return data[y * w + x] > 127
    },
    isLandAt(lat, lng) {
      const x = Math.floor(((lng + 180) / 360) * w)
      const y = Math.floor(((90 - lat) / 180) * h)
      return this.isLand(x, y)
    },
  }
}

export function loadLandMask(
  url = `${import.meta.env.BASE_URL}assets/textures/land_mask.png`
): Promise<LandMask | null> {
  if (cache) return cache
  cache = new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = "anonymous"
    img.onload = () => {
      try {
        resolve(decode(img))
      } catch {
        resolve(null)
      }
    }
    img.onerror = () => resolve(null)
    img.src = url
  })
  return cache
}

/**
 * Rejection-sample `count` points that fall on land, spread evenly over the
 * sphere. Returns a flat XYZ Float32Array on a unit sphere plus the matching
 * lat/lng, so callers can colour or label individual points.
 *
 * Using equal-area sampling (uniform in sin(lat)) avoids the dense clumping at
 * the poles you get from sampling latitude linearly.
 */
export function sampleLandPoints(
  mask: LandMask | null,
  count: number,
  radius = 1
): { positions: Float32Array; lats: Float32Array; lngs: Float32Array } {
  const positions = new Float32Array(count * 3)
  const lats = new Float32Array(count)
  const lngs = new Float32Array(count)

  let written = 0
  let guard = 0
  const maxTries = count * 140

  while (written < count && guard < maxTries) {
    guard++
    // equal-area: u uniform in [-1,1] -> lat = asin(u)
    const u = Math.random() * 2 - 1
    const lat = (Math.asin(u) * 180) / Math.PI
    const lng = Math.random() * 360 - 180

    if (mask && !mask.isLandAt(lat, lng)) continue

    const phi = ((90 - lat) * Math.PI) / 180
    const theta = ((lng + 180) * Math.PI) / 180

    const i = written * 3
    positions[i] = -radius * Math.sin(phi) * Math.cos(theta)
    positions[i + 1] = radius * Math.cos(phi)
    positions[i + 2] = radius * Math.sin(phi) * Math.sin(theta)
    lats[written] = lat
    lngs[written] = lng
    written++
  }

  // Mask missing or too slow: fill the remainder over the whole sphere so the
  // scene still reads as an Earth rather than rendering half-empty.
  while (written < count) {
    const u = Math.random() * 2 - 1
    const lat = (Math.asin(u) * 180) / Math.PI
    const lng = Math.random() * 360 - 180
    const phi = ((90 - lat) * Math.PI) / 180
    const theta = ((lng + 180) * Math.PI) / 180
    const i = written * 3
    positions[i] = -radius * Math.sin(phi) * Math.cos(theta)
    positions[i + 1] = radius * Math.cos(phi)
    positions[i + 2] = radius * Math.sin(phi) * Math.sin(theta)
    lats[written] = lat
    lngs[written] = lng
    written++
  }

  return { positions, lats, lngs }
}

/** Convert lat/lng to a position on a sphere of the given radius. */
export function latLngToVec3(
  lat: number,
  lng: number,
  radius = 1
): [number, number, number] {
  const phi = ((90 - lat) * Math.PI) / 180
  const theta = ((lng + 180) * Math.PI) / 180
  return [
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  ]
}

/** Inverse of latLngToVec3, used by the cursor readout's globe raycast. */
export function vec3ToLatLng(
  x: number,
  y: number,
  z: number
): { lat: number; lng: number } {
  const r = Math.sqrt(x * x + y * y + z * z) || 1
  const lat = 90 - (Math.acos(y / r) * 180) / Math.PI
  let lng = (Math.atan2(z, -x) * 180) / Math.PI - 180
  while (lng < -180) lng += 360
  while (lng > 180) lng -= 360
  return { lat, lng }
}
