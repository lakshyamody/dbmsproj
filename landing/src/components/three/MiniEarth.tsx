/**
 * The small rotating Earth used in the Mission section: a wireframe globe with
 * one tilted orbit ring and SomaiyaSat riding it as a bright dot.
 *
 * Renders on demand and pauses when scrolled out of view.
 */
import { useEffect, useMemo, useRef, useState } from "react"
import { Canvas, useFrame } from "@react-three/fiber"
import * as THREE from "three"

import { loadLandMask, sampleLandPoints } from "@/lib/landmask"
import { prefersReducedMotion } from "@/lib/gsap"

function Globe({ points }: { points: number }) {
  const group = useRef<THREE.Group>(null)
  const sat = useRef<THREE.Mesh>(null)
  const [geom, setGeom] = useState<THREE.BufferGeometry | null>(null)

  useEffect(() => {
    let alive = true
    loadLandMask().then((mask) => {
      if (!alive) return
      const { positions } = sampleLandPoints(mask, points, 1)
      const g = new THREE.BufferGeometry()
      g.setAttribute("position", new THREE.BufferAttribute(positions, 3))
      setGeom(g)
    })
    return () => {
      alive = false
    }
  }, [points])

  useEffect(() => () => geom?.dispose(), [geom])

  useFrame((state, dt) => {
    if (group.current) group.current.rotation.y += dt * 0.12
    if (sat.current) {
      // Ride the tilted ring.
      const t = state.clock.elapsedTime * 0.55
      const r = 1.42
      sat.current.position.set(Math.cos(t) * r, 0, Math.sin(t) * r)
    }
  })

  const ringGeom = useMemo(() => {
    const count = 256
    const pos = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const a = (i / count) * Math.PI * 2
      pos[i * 3] = Math.cos(a) * 1.42
      pos[i * 3 + 1] = 0
      pos[i * 3 + 2] = Math.sin(a) * 1.42
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3))
    return g
  }, [])

  useEffect(() => () => ringGeom.dispose(), [ringGeom])

  return (
    <>
      <group ref={group}>
        {geom && (
          <points geometry={geom}>
            <pointsMaterial
              size={0.015}
              color="#3d6bff"
              transparent
              opacity={0.95}
              sizeAttenuation
              depthWrite={false}
              blending={THREE.AdditiveBlending}
            />
          </points>
        )}
        {/* Solid body so only the near hemisphere's points show.
            This MUST be opaque: a transparent material lands in the
            transparent pass alongside the points, and with both centred on
            the origin the sort order is a coin toss — the sphere was winning
            and painting over the near-side points, leaving only a rim. Opaque
            means it draws first, writes depth, and the far-side points are
            correctly culled instead. */}
        <mesh renderOrder={-1}>
          <sphereGeometry args={[0.99, 64, 64]} />
          <meshBasicMaterial color="#050a16" />
        </mesh>
      </group>

      {/* tilted orbit ring + satellite */}
      <group rotation={[0.42, 0, 0.3]}>
        <points geometry={ringGeom}>
          <pointsMaterial
            size={0.011}
            color="#ffffff"
            transparent
            opacity={0.5}
            sizeAttenuation
            depthWrite={false}
          />
        </points>
        <mesh ref={sat}>
          <sphereGeometry args={[0.035, 16, 16]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      </group>
    </>
  )
}

export function MiniEarth({ className }: { className?: string }) {
  const wrap = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(false)
  const reduced = useMemo(() => prefersReducedMotion(), [])

  // Only render while on screen.
  useEffect(() => {
    const el = wrap.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => setActive(entry.isIntersecting),
      { rootMargin: "120px" }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <div ref={wrap} className={className}>
      {active && (
        <Canvas
          dpr={[1, 2]}
          frameloop={reduced ? "demand" : "always"}
          camera={{ position: [0, 0.55, 3.15], fov: 42 }}
          gl={{ antialias: true, alpha: true }}
          style={{ background: "transparent" }}
        >
          <Globe points={reduced ? 9000 : 22000} />
        </Canvas>
      )}
    </div>
  )
}
