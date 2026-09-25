/**
 * The pinned hero canvas: one R3F Canvas holding scenes 1-3, with scene 4
 * (line art) layered over it as SVG.
 *
 * Scroll progress arrives through a ref, so scrubbing never re-renders React.
 * Rendering pauses entirely when the hero scrolls out of view.
 */
import { Suspense, useMemo, useRef } from "react"
import { Canvas, useFrame, useThree } from "@react-three/fiber"
import * as THREE from "three"

import { PointsEarth } from "./PointsEarth"
import { TexturedEarth } from "./TexturedEarth"
import { PodAndSat } from "./PodAndSat"
import { LineArtLink } from "./LineArtLink"
import { SceneErrorBoundary } from "./SceneErrorBoundary"
import {
  SceneProgressContext,
  type SceneProgress,
  ramp,
  SCENES,
} from "@/hooks/useScrollScene"
import { isMobileViewport, prefersReducedMotion } from "@/lib/gsap"
import { vec3ToLatLng } from "@/lib/landmask"

/** Moves the camera through the four scenes and pauses when off-screen. */
function Rig({ progress }: { progress: SceneProgress }) {
  const { camera, invalidate } = useThree()
  const target = useRef(new THREE.Vector3(0, 0, 0))

  useFrame(() => {
    if (!progress.visible) return
    const p = progress.current

    // Scene 1 -> 2: pull in from far away toward the globe.
    const dive = ramp(SCENES.dive.in[0], SCENES.dive.out[1], p)
    // Scene 3: rise above the limb and swing slightly to the side.
    const deploy = ramp(SCENES.deployment.in[0], SCENES.deployment.out[1], p)

    // Dive pulls in toward the globe; deployment pulls back out so the pod
    // and cube read at their true, very small scale against the limb.
    const z = 4.0 - dive * 1.35 + deploy * 1.75
    const y = 0 + dive * 0.1 + deploy * 0.2
    const x = 0 + deploy * 0.3

    camera.position.lerp(new THREE.Vector3(x, y, z), 0.12)
    camera.lookAt(target.current)
    invalidate()
  })

  return null
}

/** Reports the point under the cursor on the globe, for the cursor readout. */
function GlobeProbe({ progress }: { progress: SceneProgress }) {
  const { camera, raycaster, pointer } = useThree()
  const sphere = useMemo(() => new THREE.Sphere(new THREE.Vector3(0, 0, 0), 1), [])
  const hit = useMemo(() => new THREE.Vector3(), [])

  useFrame(() => {
    if (!progress.visible) return
    // Only meaningful while a globe is actually on screen.
    if (progress.current > SCENES.deployment.in[0]) {
      window.__ssGlobeHit = null
      return
    }
    raycaster.setFromCamera(pointer, camera)
    const p = raycaster.ray.intersectSphere(sphere, hit)
    window.__ssGlobeHit = p ? vec3ToLatLng(p.x, p.y, p.z) : null
  })

  return null
}

export function HeroScene({
  progressRef,
  ready,
}: {
  progressRef: { current: SceneProgress }
  /** False while the intro gate is up: mount the scene but run no frames. */
  ready: boolean
}) {
  const reduced = useMemo(() => prefersReducedMotion(), [])
  const mobile = useMemo(() => isMobileViewport(), [])
  const pointCount = mobile ? 15000 : 40000

  const ctx = useMemo(() => ({ value: progressRef.current }), [progressRef])

  return (
    <SceneProgressContext.Provider value={ctx}>
      <div className="absolute inset-0">
        <Canvas
          frameloop={ready ? "always" : "never"}
          dpr={[1, 2]}
          gl={{
            antialias: true,
            alpha: true,
            powerPreference: "high-performance",
          }}
          camera={{ position: [0, 0, 4], fov: 42, near: 0.1, far: 100 }}
          style={{ background: "transparent" }}
        >
          <Suspense fallback={null}>
            <Rig progress={progressRef.current} />
            <GlobeProbe progress={progressRef.current} />
            <PointsEarth pointCount={pointCount} />
            {/* The only useLoader consumer: if its textures 404, drop just this
                scene rather than letting the throw unmount the whole page. */}
            <SceneErrorBoundary label="TexturedEarth">
              <TexturedEarth />
            </SceneErrorBoundary>
            {!reduced && <PodAndSat />}
          </Suspense>
        </Canvas>

        {/* Scene 4 rides on top as crisp vector line-art. */}
        <LineArtLink progressRef={progressRef.current} />
      </div>
    </SceneProgressContext.Provider>
  )
}

declare global {
  interface Window {
    __ssGlobeHit: { lat: number; lng: number } | null
  }
}
