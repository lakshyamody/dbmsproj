/**
 * Scene 3 — Deployment.
 *
 * Low orbit above the limb: the SomaiyaPod deployer swings its hinged door open
 * and the SomaiyaSat PocketQube slides out along the rail with a slow tumble.
 *
 * All geometry is built from primitives — an aluminium box with a chamfered
 * frame for the pod, and a stack of PCB layers with dark solar faces for the
 * satellite. Nothing here is imported artwork.
 */
import { useMemo, useRef } from "react"
import { useFrame } from "@react-three/fiber"
import * as THREE from "three"

import { SCENES, sceneOpacity, ramp, useSceneProgress } from "@/hooks/useScrollScene"

const ALU = "#c9ccd2"
const ALU_DARK = "#6f747d"
const PCB = "#1d2633"
const SOLAR = "#0a0e17"

/** The PocketQube: stacked PCB layers, dark solar faces, a whip antenna. */
function SomaiyaSat() {
  return (
    <group>
      {/* body: 5cm cube, modelled at 0.5 world units */}
      <mesh castShadow>
        <boxGeometry args={[0.5, 0.5, 0.5]} />
        <meshStandardMaterial color={PCB} metalness={0.2} roughness={0.6} />
      </mesh>

      {/* solar faces on four sides */}
      {[
        [0, 0, 0.253, 0, 0, 0],
        [0, 0, -0.253, 0, Math.PI, 0],
        [0.253, 0, 0, 0, Math.PI / 2, 0],
        [-0.253, 0, 0, 0, -Math.PI / 2, 0],
      ].map(([x, y, z, rx, ry, rz], i) => (
        <mesh key={i} position={[x, y, z]} rotation={[rx, ry, rz]}>
          <planeGeometry args={[0.44, 0.44]} />
          <meshStandardMaterial
            color={SOLAR}
            metalness={0.4}
            roughness={0.3}
            side={THREE.DoubleSide}
          />
        </mesh>
      ))}

      {/* PCB stack lines: three bright seams around the body */}
      {[-0.13, 0, 0.13].map((y) => (
        <mesh key={y} position={[0, y, 0]}>
          <boxGeometry args={[0.515, 0.012, 0.515]} />
          <meshStandardMaterial
            color="#3d6bff"
            emissive="#3d6bff"
            emissiveIntensity={0.55}
            metalness={0.2}
            roughness={0.6}
          />
        </mesh>
      ))}

      {/* top plate + whip antenna */}
      <mesh position={[0, 0.262, 0]}>
        <boxGeometry args={[0.46, 0.028, 0.46]} />
        <meshStandardMaterial color={ALU_DARK} metalness={0.25} roughness={0.4} />
      </mesh>
      <mesh position={[0.13, 0.52, 0.13]}>
        <cylinderGeometry args={[0.008, 0.008, 0.5, 6]} />
        <meshStandardMaterial color={ALU} metalness={0.3} roughness={0.3} />
      </mesh>
      <mesh position={[0.13, 0.78, 0.13]}>
        <sphereGeometry args={[0.022, 12, 12]} />
        <meshStandardMaterial
          color="#3d6bff"
          emissive="#3d6bff"
          emissiveIntensity={1.4}
        />
      </mesh>
    </group>
  )
}

/** The SomaiyaPod: an open-ended aluminium tube with a hinged door. */
function SomaiyaPod({ doorAngle }: { doorAngle: number }) {
  const door = useRef<THREE.Group>(null)

  useFrame(() => {
    if (door.current) door.current.rotation.y = -doorAngle
  })

  // Four rails forming the box walls, leaving the +Z face open for the door.
  const walls = useMemo(
    () =>
      [
        { pos: [0, 0.42, 0], size: [0.9, 0.06, 0.9] },
        { pos: [0, -0.42, 0], size: [0.9, 0.06, 0.9] },
        { pos: [0.42, 0, 0], size: [0.06, 0.9, 0.9] },
        { pos: [-0.42, 0, 0], size: [0.06, 0.9, 0.9] },
        { pos: [0, 0, -0.42], size: [0.9, 0.9, 0.06] },
      ] as const,
    []
  )

  return (
    <group>
      {walls.map((w, i) => (
        <mesh key={i} position={w.pos as unknown as [number, number, number]}>
          <boxGeometry args={w.size as unknown as [number, number, number]} />
          <meshStandardMaterial color={ALU} metalness={0.25} roughness={0.42} />
        </mesh>
      ))}

      {/* internal rails the cube slides along */}
      {[
        [0.3, 0.3],
        [-0.3, 0.3],
        [0.3, -0.3],
        [-0.3, -0.3],
      ].map(([x, y], i) => (
        <mesh key={i} position={[x, y, 0]}>
          <boxGeometry args={[0.04, 0.04, 0.84]} />
          <meshStandardMaterial color={ALU_DARK} metalness={0.3} roughness={0.5} />
        </mesh>
      ))}

      {/* hinged door, pivoting on the -X edge of the open face */}
      <group ref={door} position={[-0.42, 0, 0.44]}>
        <mesh position={[0.42, 0, 0]}>
          <boxGeometry args={[0.86, 0.86, 0.045]} />
          <meshStandardMaterial color={ALU} metalness={0.25} roughness={0.4} />
        </mesh>
        <mesh position={[0.42, 0, 0.03]}>
          <boxGeometry args={[0.6, 0.6, 0.012]} />
          <meshStandardMaterial
            color="#3d6bff"
            emissive="#3d6bff"
            emissiveIntensity={0.3}
            metalness={0.4}
            roughness={0.5}
          />
        </mesh>
      </group>

      {/* hinge barrel */}
      <mesh position={[-0.42, 0, 0.44]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.035, 0.035, 0.9, 10]} />
        <meshStandardMaterial color={ALU_DARK} metalness={0.3} roughness={0.35} />
      </mesh>
    </group>
  )
}

export function PodAndSat() {
  const group = useRef<THREE.Group>(null)
  const satGroup = useRef<THREE.Group>(null)
  const podGroup = useRef<THREE.Group>(null)
  const limb = useRef<THREE.Mesh>(null)
  const { value: progress } = useSceneProgress()

  const doorAngle = useRef(0)

  useFrame((state) => {
    const p = progress.current
    const o = sceneOpacity(SCENES.deployment, p)

    if (group.current) {
      group.current.visible = o > 0.001
      // A PocketQube is tiny; keep it tiny against the planet behind it.
      group.current.scale.setScalar(0.42 + 0.05 * o)
      group.current.position.set(0.15, 0.55, 0)
    }

    // Local timeline across the WHOLE deployment window, including its
    // crossfades — otherwise the release is crammed into a sliver of scroll.
    const t = ramp(SCENES.deployment.in[0], SCENES.deployment.out[1], p)

    // Door swings open over the first third.
    doorAngle.current = ramp(0.08, 0.38, t) * (Math.PI * 0.72)

    if (satGroup.current) {
      // Slide out along the rails (+Z local), then drift free with a tumble.
      const slide = ramp(0.34, 0.68, t)
      const drift = ramp(0.68, 1, t)
      satGroup.current.position.z = 0.02 + slide * 1.45 + drift * 2.6
      satGroup.current.position.y = drift * 0.3
      satGroup.current.rotation.x = drift * 1.1 + state.clock.elapsedTime * 0.14 * drift
      satGroup.current.rotation.y = slide * 0.2 + drift * 1.7
      satGroup.current.rotation.z = drift * 0.4
    }

    if (podGroup.current) {
      // Three-quarter view: the opening points to camera-right so the cube
      // travels across frame instead of straight at the lens.
      const recoil = ramp(0.34, 0.6, t)
      podGroup.current.position.z = -recoil * 0.14
      podGroup.current.rotation.y = t * 0.08
    }

    if (limb.current) {
      const m = limb.current.material as THREE.MeshBasicMaterial
      m.opacity = o * 0.5
    }

    // Fade every material in the scene together.
    if (group.current) {
      group.current.traverse((obj) => {
        const mesh = obj as THREE.Mesh
        if (!mesh.isMesh) return
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
        for (const m of mats) {
          if (!m) continue
          const mm = m as THREE.Material
          mm.transparent = true
          mm.opacity = o
          mm.depthWrite = o > 0.6
        }
      })
    }
  })

  return (
    <group ref={group} position={[0, 0, 0]}>
      <ambientLight intensity={0.9} />
      <hemisphereLight args={["#cfe0ff", "#0a0f1e", 1.1]} />
      <directionalLight position={[4, 3, 5]} intensity={3.2} color="#ffffff" />
      <directionalLight position={[-5, 1, 2]} intensity={1.3} color="#8fb0ff" />
      <directionalLight position={[0, -3, -4]} intensity={0.7} color="#3d6bff" />

      {/* One frame for both, so the cube slides along the pod's own rails. */}
      <group position={[-0.5, 0, 0]} rotation={[0.17, -0.62, 0]}>
        <group ref={podGroup} rotation={[0, 0, 0]}>
          <SomaiyaPod doorAngle={doorAngle.current} />
        </group>
        <group ref={satGroup} position={[0, 0, 0]}>
          <SomaiyaSat />
        </group>
      </group>

      {/* The Earth's limb curving across the bottom of frame. */}
      <mesh ref={limb} position={[0, -19, -6]} rotation={[0, 0, 0]}>
        <sphereGeometry args={[18, 96, 48]} />
        <meshBasicMaterial
          color="#08142e"
          transparent
          opacity={0}
          depthWrite={false}
        />
      </mesh>
    </group>
  )
}
