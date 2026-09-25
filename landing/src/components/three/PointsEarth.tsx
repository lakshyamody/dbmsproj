/**
 * Scene 1 — Constellation.
 *
 * The Earth drawn as a cloud of glowing blue points sampled from the land mask,
 * wrapped in a few faint dotted orbit shells. Points are additively blended so
 * dense continents read brighter than sparse island chains.
 */
import { useEffect, useMemo, useRef, useState } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"

import { loadLandMask, sampleLandPoints } from "@/lib/landmask"
import { PALETTE } from "@/lib/palette"
import { SCENES, sceneOpacity, useSceneProgress } from "@/hooks/useScrollScene"

/** A soft round sprite so points render as dots, not squares. */
function makeDotTexture(): THREE.Texture {
  const size = 64
  const c = document.createElement("canvas")
  c.width = c.height = size
  const ctx = c.getContext("2d")!
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  g.addColorStop(0, "rgba(255,255,255,1)")
  g.addColorStop(0.35, "rgba(255,255,255,0.85)")
  g.addColorStop(1, "rgba(255,255,255,0)")
  ctx.fillStyle = g
  ctx.fillRect(0, 0, size, size)
  const tex = new THREE.CanvasTexture(c)
  tex.needsUpdate = true
  return tex
}

function OrbitShell({
  radius,
  tilt,
  spin,
  opacity,
}: {
  radius: number
  tilt: [number, number, number]
  spin: number
  opacity: number
}) {
  const ref = useRef<THREE.Points>(null)

  const geometry = useMemo(() => {
    const count = 220
    const pos = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2
      pos[i * 3] = Math.cos(a) * radius
      pos[i * 3 + 1] = 0
      pos[i * 3 + 2] = Math.sin(a) * radius
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3))
    return g
  }, [radius])

  useFrame((_, dt) => {
    if (ref.current) ref.current.rotation.y += spin * dt
  })

  useEffect(() => () => geometry.dispose(), [geometry])

  return (
    <points ref={ref} geometry={geometry} rotation={tilt}>
      <pointsMaterial
        size={0.016}
        color={PALETTE.accent}
        transparent
        opacity={opacity}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

export function PointsEarth({ pointCount = 40000 }: { pointCount?: number }) {
  const group = useRef<THREE.Group>(null)
  const pointsRef = useRef<THREE.Points>(null)
  const matRef = useRef<THREE.PointsMaterial>(null)
  const shellMat = useRef<number>(0)
  const { value: progress } = useSceneProgress()

  const [geometry, setGeometry] = useState<THREE.BufferGeometry | null>(null)
  const dotTexture = useMemo(() => makeDotTexture(), [])

  // Sample the land mask once it decodes.
  useEffect(() => {
    let alive = true
    loadLandMask().then((mask) => {
      if (!alive) return
      const { positions } = sampleLandPoints(mask, pointCount, 1)
      const g = new THREE.BufferGeometry()
      g.setAttribute("position", new THREE.BufferAttribute(positions, 3))
      g.computeBoundingSphere()
      setGeometry(g)
    })
    return () => {
      alive = false
    }
  }, [pointCount])

  useEffect(() => {
    return () => {
      geometry?.dispose()
      dotTexture.dispose()
    }
  }, [geometry, dotTexture])

  useFrame((_, dt) => {
    const p = progress.current
    const o = sceneOpacity(SCENES.constellation, p)
    shellMat.current = o

    if (matRef.current) {
      matRef.current.opacity = o
      // Points swell very slightly as the scene establishes itself.
      matRef.current.size = 0.0085 + 0.002 * o
    }
    if (group.current) {
      group.current.visible = o > 0.001
      group.current.rotation.y += dt * 0.055
      // Pull back a touch as the dive begins, so scene 2 feels like an approach.
      const s = 1 + 0.06 * p
      group.current.scale.setScalar(s)
    }
  })

  return (
    <group ref={group}>
      {geometry && (
        <points ref={pointsRef} geometry={geometry}>
          <pointsMaterial
            ref={matRef}
            map={dotTexture}
            size={0.0095}
            color={PALETTE.accent}
            transparent
            opacity={0}
            sizeAttenuation
            depthWrite={false}
            blending={THREE.AdditiveBlending}
            alphaTest={0.01}
          />
        </points>
      )}

      {/* Faint dotted orbit shells at different inclinations. */}
      <OrbitShell radius={1.34} tilt={[0.32, 0, 0.12]} spin={0.09} opacity={0.42} />
      <OrbitShell radius={1.52} tilt={[-0.5, 0.3, -0.18]} spin={-0.06} opacity={0.3} />
      <OrbitShell radius={1.74} tilt={[0.16, 0.9, 0.42]} spin={0.045} opacity={0.22} />
      <OrbitShell radius={1.96} tilt={[-0.22, -0.4, 0.62]} spin={-0.035} opacity={0.15} />
    </group>
  )
}
