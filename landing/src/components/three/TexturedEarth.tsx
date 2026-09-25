/**
 * Scene 2 — Dive.
 *
 * The point cloud resolves into a real Earth. A custom shader blends the day
 * texture into the night lights along the terminator and adds a fresnel
 * atmosphere rim, so the limb glows blue against the black page.
 *
 * The camera swings toward India (roughly the KJSSE ground station) as the
 * scene progresses, which sets up the deployment scene overhead.
 */
import { useEffect, useMemo, useRef } from "react"
import { useFrame, useLoader } from "@react-three/fiber"
import * as THREE from "three"

import { SCENES, sceneOpacity, ramp, useSceneProgress } from "@/hooks/useScrollScene"

const EARTH_VERT = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vViewDir;

  void main() {
    vUv = uv;
    vec4 worldPos = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - worldPos.xyz);
    gl_Position = projectionMatrix * viewMatrix * worldPos;
  }
`

const EARTH_FRAG = /* glsl */ `
  uniform sampler2D dayMap;
  uniform sampler2D nightMap;
  uniform sampler2D cloudMap;
  uniform vec3  sunDirection;
  uniform float opacity;
  uniform float cloudStrength;
  uniform float cloudOffset;
  uniform vec3  rimColor;

  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vViewDir;

  void main() {
    vec3 day   = texture2D(dayMap,   vUv).rgb;
    vec3 night = texture2D(nightMap, vUv).rgb;

    // Terminator: soft band where the sun grazes the surface.
    float lambert = dot(normalize(vNormalW), normalize(sunDirection));
    float dayMix  = smoothstep(-0.18, 0.28, lambert);

    // Night side is the city lights, warmed slightly and kept dim.
    vec3 lights = night * 1.5;
    vec3 color  = mix(lights, day * 1.02, dayMix);

    // Cool the whole globe a touch so it sits in the blue palette.
    color = mix(color, color * vec3(0.82, 0.90, 1.12), 0.35);

    // Clouds, composited in the same shader so they take exactly the same
    // day/night lighting as the surface under them, and drift with an offset
    // rather than needing a second mesh.
    float cloud = texture2D(cloudMap, vec2(vUv.x + cloudOffset, vUv.y)).r;
    color = mix(color, vec3(1.0) * max(dayMix, 0.06), cloud * cloudStrength);

    // Fresnel atmosphere rim.
    float fres = 1.0 - max(dot(normalize(vNormalW), normalize(vViewDir)), 0.0);
    fres = pow(fres, 2.6);
    color += rimColor * fres * 1.35;

    gl_FragColor = vec4(color, opacity);
  }
`

export function TexturedEarth() {
  const group = useRef<THREE.Group>(null)
  const mesh = useRef<THREE.Mesh>(null)
  const matRef = useRef<THREE.ShaderMaterial>(null)
  const glowRef = useRef<THREE.Mesh>(null)
  const { value: progress } = useSceneProgress()

  const base = import.meta.env.BASE_URL
  const [dayMap, nightMap] = useLoader(THREE.TextureLoader, [
    `${base}assets/textures/earth_day.jpg`,
    `${base}assets/textures/earth_night.jpg`,
  ])

  // Loaded outside useLoader on purpose: useLoader suspends and throws, so a
  // missing clouds file would take the whole textured Earth down with it.
  // Here it just stays at strength 0 and the globe renders cloudless.
  useEffect(() => {
    let alive = true
    new THREE.TextureLoader().load(
      `${base}assets/textures/earth_clouds.jpg`,
      (tex) => {
        if (!alive) return
        tex.wrapS = THREE.RepeatWrapping
        tex.colorSpace = THREE.NoColorSpace
        const u = matRef.current?.uniforms
        if (u) {
          u.cloudMap.value = tex
          u.cloudStrength.value = 0.55
        }
      },
      undefined,
      () => {
        /* no clouds; the Earth is still fine */
      }
    )
    return () => {
      alive = false
    }
  }, [base])

  useEffect(() => {
    for (const t of [dayMap, nightMap]) {
      t.colorSpace = THREE.SRGBColorSpace
      t.anisotropy = 4
      t.needsUpdate = true
    }
  }, [dayMap, nightMap])

  const uniforms = useMemo(
    () => ({
      dayMap: { value: dayMap },
      nightMap: { value: nightMap },
      cloudMap: { value: null as THREE.Texture | null },
      sunDirection: { value: new THREE.Vector3(1, 0.25, 0.6).normalize() },
      opacity: { value: 0 },
      cloudStrength: { value: 0 },
      cloudOffset: { value: 0 },
      rimColor: { value: new THREE.Color("#3d6bff") },
    }),
    [dayMap, nightMap]
  )

  useFrame(() => {
    const p = progress.current
    const o = sceneOpacity(SCENES.dive, p)

    if (matRef.current) {
      matRef.current.uniforms.opacity.value = o
      matRef.current.uniforms.cloudOffset.value += 0.00002
    }
    if (glowRef.current) {
      const m = glowRef.current.material as THREE.MeshBasicMaterial
      m.opacity = o * 0.16
    }

    if (group.current) {
      group.current.visible = o > 0.001
      // Rotate so India faces the camera as the dive completes.
      const t = ramp(SCENES.dive.in[0], SCENES.dive.out[1], p)
      // End with India (~22N, 78E) squarely facing the camera: that puts the
      // KJSSE ground station under the spacecraft when scene 3 begins.
      group.current.rotation.y = 2.35 + t * 0.58
      group.current.rotation.x = 0.06 + t * 0.26
      // Approach: grow and drift down so we finish just above the limb.
      const s = 1.0 + t * 0.24
      group.current.scale.setScalar(s)
      group.current.position.y = -t * 0.3
    }
  })

  return (
    <group ref={group}>
      <mesh ref={mesh}>
        <sphereGeometry args={[1, 96, 96]} />
        <shaderMaterial
          ref={matRef}
          vertexShader={EARTH_VERT}
          fragmentShader={EARTH_FRAG}
          uniforms={uniforms}
          transparent
          depthWrite={false}
        />
      </mesh>

      {/* Outer atmosphere shell, back-faces only, for the halo past the limb. */}
      <mesh ref={glowRef} scale={1.055}>
        <sphereGeometry args={[1, 64, 64]} />
        <meshBasicMaterial
          color="#3d6bff"
          transparent
          opacity={0}
          side={THREE.BackSide}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
    </group>
  )
}
