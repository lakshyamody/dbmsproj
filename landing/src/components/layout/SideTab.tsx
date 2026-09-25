/** Rotated tab pinned to the right edge, linking to the live dashboard. */
import { DASHBOARD_URL } from "@/lib/config"

export function SideTab() {
  return (
    <a
      href={DASHBOARD_URL}
      target="_blank"
      rel="noreferrer"
      className="group fixed right-0 top-1/2 z-40 hidden -translate-y-1/2 md:block"
      aria-label="Enter Mission Control"
    >
      <span
        className="mono-label flex items-center gap-3 border-y border-l border-white/[0.12] bg-black/60 px-3 py-5 text-[#8a8f98] backdrop-blur-xl transition-colors duration-300 group-hover:border-[#3d6bff]/60 group-hover:bg-[#3d6bff]/10 group-hover:text-white"
        style={{ writingMode: "vertical-rl" }}
      >
        <span
          className="inline-block size-1.5 rounded-full bg-[#3d6bff]"
          style={{ boxShadow: "0 0 10px #3d6bff" }}
        />
        Enter Mission Control
      </span>
    </a>
  )
}
