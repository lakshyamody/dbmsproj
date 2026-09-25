/**
 * The Earth's limb glowing across the bottom of the CTA section. Pure CSS
 * gradients rather than WebGL — it is decorative, and a fourth canvas would
 * cost more than it is worth.
 */
export function HorizonEarth({ className = "" }: { className?: string }) {
  return (
    <div className={`pointer-events-none overflow-hidden ${className}`} aria-hidden="true">
      {/* atmosphere bloom */}
      <div
        className="absolute bottom-[-58%] left-1/2 h-[120vh] w-[190vw] -translate-x-1/2 rounded-[50%]"
        style={{
          background:
            "radial-gradient(closest-side, rgba(61,107,255,0.30), rgba(61,107,255,0.10) 58%, transparent 74%)",
          filter: "blur(18px)",
        }}
      />
      {/* planet body */}
      <div
        className="absolute bottom-[-62%] left-1/2 h-[120vh] w-[180vw] -translate-x-1/2 rounded-[50%] border-t border-[#3d6bff]/70"
        style={{
          background:
            "radial-gradient(closest-side at 50% 0%, #0a1330 0%, #04070f 45%, #000 78%)",
        }}
      />
      {/* terminator highlight */}
      <div
        className="absolute bottom-[-2%] left-1/2 h-px w-[120vw] -translate-x-1/2"
        style={{
          background:
            "linear-gradient(90deg, transparent, rgba(61,107,255,0.8), transparent)",
        }}
      />
    </div>
  )
}
