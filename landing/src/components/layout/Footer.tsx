/**
 * Footer, sitting over the Earth's horizon, with a small line-art SomaiyaSat
 * drifting across it on a long loop.
 */
import { useRef } from "react"

import { Wordmark, SectionLabel } from "@/components/brand/Brand"
import { gsap, useGSAP, prefersReducedMotion } from "@/lib/gsap"
import { MISSION } from "@/lib/config"

/** Original line-art satellite: body, two panels, antenna. */
function DriftingSat({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 54" fill="none" className={className} aria-hidden="true">
      <rect
        x="48"
        y="16"
        width="24"
        height="22"
        stroke="currentColor"
        strokeWidth="1.2"
      />
      <path d="M48 22 H72 M48 32 H72" stroke="currentColor" strokeWidth="0.8" opacity="0.5" />
      {/* panels */}
      <rect x="10" y="20" width="34" height="14" stroke="currentColor" strokeWidth="1.1" />
      <rect x="76" y="20" width="34" height="14" stroke="currentColor" strokeWidth="1.1" />
      <path
        d="M19 20 V34 M28 20 V34 M37 20 V34 M85 20 V34 M94 20 V34 M103 20 V34"
        stroke="currentColor"
        strokeWidth="0.7"
        opacity="0.45"
      />
      <path d="M44 27 H48 M72 27 H76" stroke="currentColor" strokeWidth="1.1" />
      {/* antenna */}
      <path d="M60 16 V6" stroke="currentColor" strokeWidth="1.1" />
      <circle cx="60" cy="4" r="2.4" fill="#3d6bff" />
    </svg>
  )
}

export function Footer() {
  const root = useRef<HTMLElement>(null)

  useGSAP(
    () => {
      if (prefersReducedMotion()) return
      gsap.fromTo(
        ".footer-sat",
        { xPercent: -30 },
        {
          xPercent: 1100,
          duration: 46,
          ease: "none",
          repeat: -1,
          delay: 2,
        }
      )
    },
    { scope: root }
  )

  return (
    <footer ref={root} className="relative overflow-hidden border-t border-white/[0.12] bg-black">
      {/* horizon glow */}
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(61,107,255,.7), transparent)",
        }}
      />
      <div
        className="pointer-events-none absolute left-1/2 top-0 h-[300px] w-[160%] -translate-x-1/2 rounded-[50%]"
        style={{
          background:
            "radial-gradient(60% 100% at 50% 0%, rgba(61,107,255,.16), transparent 70%)",
        }}
      />

      {/* drifting satellite */}
      <div className="pointer-events-none absolute left-0 top-8 w-full">
        <DriftingSat className="footer-sat w-[92px] text-white/25" />
      </div>

      <div className="shell relative z-10 py-20 md:py-24">
        <div className="grid gap-12 md:grid-cols-[1.2fr_1fr_1fr]">
          <div>
            <Wordmark className="text-[22px]" />
            <p className="mt-4 max-w-[38ch] text-sm leading-relaxed text-[#8a8f98]">
              A ground-station database for a PocketQube that has to choose what
              to say in the few minutes a day anyone can hear it.
            </p>
            <p className="mt-4 max-w-[44ch] text-[12px] leading-relaxed text-[#8a8f98]/70">
              {MISSION.useCaseTitle}
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <SectionLabel>Project</SectionLabel>
            <p className="text-sm text-white/85">{MISSION.course}</p>
            <p className="text-sm text-[#8a8f98]">{MISSION.college}</p>
            <p className="text-sm text-[#8a8f98]">
              Based on AI use case{" "}
              <span className="font-mono text-white/80">{MISSION.useCase}</span>
              <br />
              <span className="text-white/60">{MISSION.vertical}</span>
            </p>
            <p className="text-sm text-[#8a8f98]">
              Beneficiaries
              <br />
              <span className="text-white/85">{MISSION.beneficiaries}</span>
            </p>
            <p className="text-sm text-[#8a8f98]">
              Team: <span className="text-white/70">[ your names here ]</span>
            </p>
          </div>

          <div className="flex flex-col gap-3">
            <SectionLabel>Credits</SectionLabel>
            <div className="flex flex-col gap-3 text-sm text-[#8a8f98]">
              <span>Faculty owners</span>
              {MISSION.faculty.map((f) => (
                <span key={f.name} className="block leading-relaxed">
                  <span className="text-white/85">{f.name}</span>
                  <br />
                  {f.role}
                  <br />
                  <span className="text-white/60">{f.institute}</span>
                </span>
              ))}
            </div>
            <p className="text-sm text-[#8a8f98]">
              Collaborating organization
              <br />
              <span className="text-white/85">{MISSION.collaborator}</span>
            </p>
            <p className="text-sm text-[#8a8f98]">
              Earth imagery: <span className="text-white/85">NASA</span>
            </p>
          </div>
        </div>

        <div className="mt-16 flex flex-col gap-4 border-t border-white/[0.12] pt-8 md:flex-row md:items-center md:justify-between">
          <span className="mono-label text-[#8a8f98]">
            © {new Date().getFullYear()} SomaiyaSat Ground Control
          </span>
          <span className="mono-label text-[#8a8f98]">
            Built with PostgreSQL · Streamlit · React
          </span>
        </div>
      </div>
    </footer>
  )
}
